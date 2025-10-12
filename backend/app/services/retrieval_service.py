# retriever.py
from pathlib import Path
from typing import List, Tuple, Optional
import re
import math
import hashlib
from unicodedata import normalize as _unicode_normalize

from langchain.vectorstores import FAISS
from sklearn.feature_extraction.text import TfidfVectorizer

from rank_bm25 import BM25Okapi
import numpy as np

from .loaders import get_vectorstore, get_cross_encoder, get_embedder, get_complexity_classifier



# --- Context shaping helpers ---

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

# NOTE: stopword removal is provided as a helper but is NOT applied by default
# because it can harm dense embeddings (e.g., removing "not", dates, etc.).

def remove_stopwords(query: str) -> str:
    """
    Remove stopwords from the query using sklearn's ENGLISH_STOP_WORDS.
    (Provided as an optional utility — do NOT call it by default.)
    """
    query_tokens = query.split()
    query_without_stopwords = [word for word in query_tokens if word.lower() not in ENGLISH_STOP_WORDS]
    return " ".join(query_without_stopwords)


def _bookend(docs):
    """Interleave to put strong evidence at both start and end."""
    left, right = [], []
    for i, d in enumerate(docs):
        (left if i % 2 == 0 else right).append(d)
    return left + right[::-1]


# --- simple whitespace/regex tokenizer (Unicode normalized) ---
_TOKEN_SPLIT = re.compile(r"[^\w]+", flags=re.UNICODE)

def _tok(text: str) -> list[str]:
    # Normalize unicode (NFKC) to handle diacritics / composed characters
    txt = _unicode_normalize("NFKC", text or "")
    return [t for t in _TOKEN_SPLIT.split(txt.lower()) if t]


# Optional tiny cache so we don't rebuild BM25 every call
_BM25_CACHE = {
    "hash": None,
    "bm25": None,
    "docs": None,
    "tokens": None,
}


def _docs_hash(docs_list: List) -> str:
    h = hashlib.sha1()
    for d in docs_list:
        # include source/page metadata if available so caching is safer
        meta = d.metadata.get("source", "") + "|" + str(d.metadata.get("page", ""))
        h.update(meta.encode("utf-8"))
        h.update(d.page_content.encode('utf-8'))
    return h.hexdigest()


def _get_bm25(all_docs) -> tuple[BM25Okapi, list, list[list[str]]]:
    docs_list = list(all_docs)
    cur_hash = _docs_hash(docs_list) if docs_list else None
    if _BM25_CACHE["hash"] == cur_hash and _BM25_CACHE["bm25"] is not None:
        return _BM25_CACHE["bm25"], _BM25_CACHE["docs"], _BM25_CACHE["tokens"]

    tokens = [_tok(d.page_content) for d in docs_list]
    bm25 = BM25Okapi(tokens)

    _BM25_CACHE.update({"hash": cur_hash, "bm25": bm25, "docs": docs_list, "tokens": tokens})
    return bm25, docs_list, tokens


# ---------- Dense + BM25 candidate fetchers & fusion ----------
def fetch_candidates(
    vectorstore: FAISS,
    query: str,
    fetch_k: int = 40,
    min_similarity: Optional[float] = None,  # None => no thresholding
) -> Tuple[List, List[float]]:
    """
    Dense candidates from FAISS, returning (docs, scores).
    Heuristically detects whether FAISS returned distances (lower=better) or
    similarities (higher=better) and converts to similarity in [ -inf, +inf ]
    for consistent downstream use.
    """
    pairs = vectorstore.similarity_search_with_relevance_scores(query, k=fetch_k)
    print(f"[DEBUG] Retrieved {len(pairs)} dense candidates for query='{query}'")

    # Quick heuristic: look at sample scores to decide whether they are distances.
    sample_scores = [float(s) for _, s in pairs[:5]] if pairs else []
    convert_distance_to_sim = False
    if sample_scores:
        # If scores are typically > 1.5 it's likely L2 distances on normalized vectors.
        if max(sample_scores) > 1.5:
            convert_distance_to_sim = True

    docs, scores = [], []
    for d, s_raw in pairs:
        s = float(s_raw)
        if convert_distance_to_sim:
            # Assuming normalized vectors, cosine_sim ~= 1 - 0.5 * (L2)^2 sometimes,
            # but a safe simple conversion is sim = 1 - s (works if index stored (1 - cos)).
            # If you know the exact metric you should replace this conversion.
            s = 1.0 - s

        # Threshold only if explicitly requested
        if (min_similarity is None) or (s >= min_similarity):
            docs.append(d)
            scores.append(s)

    print(f"[DEBUG] After threshold filter (min_similarity={min_similarity}): kept={len(docs)}")
    return docs, scores


def fetch_bm25_candidates_query(
    query: str,
    bm25: BM25Okapi,
    docs_list: List,
    k: int = 40,
    eps: float = 1e-9,
) -> Tuple[List, List[float]]:
    """
    Return top-k BM25 hits (by raw score) for the query. Avoid absolute thresholds
    on raw BM25 scores because they are corpus-dependent. Keep only documents
    with a non-zero BM25 score (eps) and then slice top-k.
    """
    q_tokens = _tok(query)
    scores = bm25.get_scores(q_tokens)  # shape: [num_docs]
    order = np.argsort(scores)[::-1]    # best → worst

    # keep only passages with a real lexical match (score > eps)
    nonzero_idx = [i for i in order if scores[i] > eps]

    k_eff = min(k, len(nonzero_idx))
    idx = nonzero_idx[:k_eff]

    out_docs = [docs_list[i] for i in idx]
    out_scores = [float(scores[i]) for i in idx]

    max_s = float(scores[order[0]]) if len(order) else 0.0
    print(f"[DEBUG] BM25: total={len(docs_list)} nonzero={len(nonzero_idx)} returned={k_eff} requested_k={k} max_score={max_s:.4f}")
    return out_docs, out_scores


def _minmax(xs: List[float]) -> List[float]:
    if not xs:
        return xs
    lo, hi = min(xs), max(xs)
    rng = hi - lo
    # fallback: if range tiny, normalize by max absolute to preserve signal
    if rng <= 1e-6:
        m = max(abs(x) for x in xs) or 1.0
        return [x / m for x in xs]
    return [(x - lo) / rng for x in xs]


def fuse_candidates(
    dense_docs: List, dense_scores: List[float],
    bm25_docs: List, bm25_scores: List[float],
    alpha: float = 0.7  # weight for dense; (1-alpha) for BM25
) -> List:
    """
    Min-max normalize scores per signal, then weighted-sum fuse and sort.
    Returns a deduplicated doc list ordered by fused score.
    """
    dense_norm = _minmax(dense_scores)
    bm25_norm = _minmax(bm25_scores)

    def key(d):
        # stable dedupe key: use source,page, and a content sha1 (deterministic)
        content_hash = hashlib.sha1(d.page_content.encode('utf-8')).hexdigest()
        return (d.metadata.get("source"), d.metadata.get("page"), content_hash)

    table = {}
    for d, s in zip(dense_docs, dense_norm):
        k = key(d)
        table.setdefault(k, {"doc": d, "dense": 0.0, "bm25": 0.0})
        table[k]["dense"] = max(table[k]["dense"] , s)

    for d, s in zip(bm25_docs, bm25_norm):
        k = key(d)
        table.setdefault(k, {"doc": d, "dense": 0.0, "bm25": 0.0})
        table[k]["bm25"] = max(table[k]["bm25"], s)

    fused = []
    for v in table.values():
        final = alpha * v["dense"] + (1 - alpha) * v["bm25"]
        fused.append((v["doc"], final))
    fused.sort(key=lambda x: x[1], reverse=True)
    docs = [d for d, _ in fused]
    print(f"[DEBUG] Fused unique candidates: {len(docs)}")
    return docs


def _sigmoid(x: float) -> float:
    try:
        if x >= 0:
            z = math.exp(-x)
            return 1.0 / (1.0 + z)
        else:
            z = math.exp(x)
            return z / (1.0 + z)
    except OverflowError:
        return 0.0 if x < 0 else 1.0


# Small CE cache + batched prediction helper
_CE_MODEL = {"model": None}

def _ce_predict_batched(ce, pairs, batch_size=64):
    out = []
    for i in range(0, len(pairs), batch_size):
        batch = pairs[i:i+batch_size]
        out.extend(list(ce.predict(batch)))
    return np.array(out)


def rerank_with_ce(
    query: str,
    docs: List,
    *,
    min_score: float = 0.0,
    normalize: bool = True,
    top_k: int | None = None,
    top_n_debug: int = 5
) -> Tuple[List, List[float]]:
    """
    Rerank with cross-encoder. Predictions are batched and the CE model is cached.
    Calibrate `min_score` externally if you plan to filter by absolute thresholds.
    """
    if not docs:
        return [], []

    # get cached CE
    if _CE_MODEL["model"] is None:
        _CE_MODEL["model"] = get_cross_encoder()
    ce = _CE_MODEL["model"]

    pairs = [(query, d.page_content) for d in docs]
    raw_scores = _ce_predict_batched(ce, pairs, batch_size=64)  # numpy array (logits)

    if normalize:
        scores = [_sigmoid(float(s)) for s in raw_scores]
    else:
        scores = [float(s) for s in raw_scores]

    ranked = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)

    # threshold filter (only if min_score is not None)
    if min_score is not None:
        ranked = [(d, s) for (d, s) in ranked if s >= min_score]

    if top_k is not None:
        ranked = ranked[:top_k]

    ranked_docs, ranked_scores = (list(x) for x in zip(*ranked)) if ranked else ([], [])

    print(f"[DEBUG] CE total_in={len(docs)} kept={len(ranked_docs)} min_score={min_score} normalize={normalize} top_k={top_k}")
    for i, (doc, score) in enumerate(zip(ranked_docs[:top_n_debug], ranked_scores[:top_n_debug])):
        snippet = doc.page_content[:80].replace("\n", " ")
        print(f"[DEBUG] CE score={score:.4f} | Doc {i}: {snippet}...")

    return ranked_docs, ranked_scores


# ---------- Main search ----------

async def search_vectorstore(
    query: str,
    index_dir: str,
    k: int = 10,
    fetch_k: int = 40,
    min_ce_score: float = 0.0,
    allow_unsafe: bool = False,
    expansion_top_n: int = 3,
    use_hybrid: bool = True,
    alpha_dense: float = 0.7,
    bm25_k: int = 40,
    source: Optional[str] = None,
    should_strip_stopwords: bool = False,
) -> Tuple[str, List[Tuple[str, str]]]:

    """
    Hybrid retrieval pipeline.
    - stopword stripping is OFF by default (can be enabled with should_strip_stopwords=True)
    - if `source` is provided we filter candidates by metadata instead of rebuilding FAISS index.
    """

    vectorstore = get_vectorstore(allow_unsafe=True)

    all_docs = list(vectorstore.docstore._dict.values())
   

    # If user asks to filter BM25 by source, build BM25 over that subset only;
    # but avoid rebuilding the dense FAISS index per call (expensive).
    if source:
        bm25_docs = [d for d in all_docs if d.metadata.get("source") == source]
        if not bm25_docs:
            return "", []
        bm25_source_iter = bm25_docs
    else:
        bm25_source_iter = all_docs


    #check query complexity
    classifier = get_complexity_classifier()
    query_complexity = classifier(query)
    print(query_complexity)
    best_result = max(query_complexity, key=lambda x: x['score'])

# 2. Extract the label and score
    predicted_label = best_result['label']
    confidence_score = best_result['score']

    print(f"Predicted Label: {predicted_label}, Confidence Score: {confidence_score}")

    if predicted_label == 'LABEL_0':
        # Strategy: Max Efficiency (Less is more)
        fetch_k = 10
        bm25_k = 10    # Fewer candidates needed
        k = 3                # Answer likely in 2-3 chunks
        use_hybrid = True   # Skip BM25 fusion for speed
        min_ce_score = 0.7   # Stricter relevance filter
        # Pure Dense (semantic) search

        print("[ADAPTIVE] Using Easy Mode: Dense Search Only (k=3), High Efficiency")

    elif predicted_label == 'LABEL_1':
        # Strategy: Balanced (Hybrid RAG) - Use existing default parameters
        fetch_k = 40
        bm25_k = 40    # Standard candidates
        k = 5                # Standard chunks
        use_hybrid = True    # Use Hybrid (Default alpha=0.7)
        min_ce_score = 0.7 # Rely on top-k, no threshold
   

        print("[ADAPTIVE] Using Medium Mode: Hybrid RAG (k=5), Balanced Accuracy")

    elif predicted_label == 'LABEL_2':
        # Strategy: Max Accuracy (High Recall, Deep Search)
        fetch_k = 80
        bm25_k = 80,      # Retrieve more candidates for CE
        k = 10               # Max number of chunks to ensure synthesis
        use_hybrid = True    # Use Hybrid Search
        alpha_dense = 0.5    # Evenly balance semantic (Dense) and keyword (BM25) recall
        min_ce_score = 0.7   # Do not discard *any* relevant candidate before final top-k

        print("[ADAPTIVE] Using Hard Mode: Deep Hybrid Search (k=10), Max Recall")


    # optional stopword stripping (disabled by default)
    if should_strip_stopwords:
        query_to_use = remove_stopwords(query)
    else:
        query_to_use = query

    print(query_to_use)

    # --- Build BM25 (cached) if hybrid ---
    if use_hybrid:
        bm25, docs_list, _ = _get_bm25(bm25_source_iter)

    # 1) Recall stage (dense retrieval)
    dense_docs, dense_scores = fetch_candidates(vectorstore, query_to_use, fetch_k=fetch_k)

    # If source filtering requested, filter dense candidates by metadata rather than rebuilding index
    if source:
        filtered = [(d, s) for d, s in zip(dense_docs, dense_scores) if d.metadata.get("source") == source]
        dense_docs = [d for d, _ in filtered]
        dense_scores = [s for _, s in filtered]

    if use_hybrid:
        bm25_docs, bm25_scores = fetch_bm25_candidates_query(query_to_use, bm25, docs_list, k=bm25_k)
        candidates = fuse_candidates(dense_docs, dense_scores, bm25_docs, bm25_scores, alpha=alpha_dense)
    else:
        candidates = dense_docs

    # 2) Precision stage (CE rerank)
    ranked_docs, ranked_scores = rerank_with_ce(query_to_use, candidates)

    # 3) Optional CE threshold
    if min_ce_score and ranked_docs:
        keep_docs, keep_scores = [], []
        for d, s in zip(ranked_docs, ranked_scores):
            if s >= min_ce_score:
                keep_docs.append(d)
                keep_scores.append(s)
        print(f"[DEBUG] Filtered out {len(ranked_docs) - len(keep_docs)} docs below CE threshold={min_ce_score}")
        ranked_docs, ranked_scores = keep_docs, keep_scores

    # 4) Top-k
    docs = ranked_docs[:k] if ranked_docs else []
    docs = _bookend(docs)
    print(f"[DEBUG] Returning {len(docs)} final docs (top-k={k})")

    # 5) Outputs
    context_parts = []
    for idx, d in enumerate(docs, 1):
        source = d.metadata.get("source", "unknown")
        page = d.metadata.get("page", "?")
        chunk = d.page_content.strip()

        structured = f"[{idx}] Source: {source}, Page: {page}\nContent: {chunk}"
        context_parts.append(structured)

        context = "\n\n".join(context_parts)
       
    context = "\n\n".join(context_parts)
    print(context)

    return context, []
