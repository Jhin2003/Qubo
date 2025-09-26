# retriever.py
from pathlib import Path
from typing import List, Tuple
import re
import math

from langchain.vectorstores import FAISS
from sklearn.feature_extraction.text import TfidfVectorizer

from rank_bm25 import BM25Okapi
import numpy as np

from .loaders import get_vectorstore, get_cross_encoder


# --- Context shaping helpers ---

def _bookend(docs):
    """Interleave to put strong evidence at both start and end."""
    left, right = [], []
    for i, d in enumerate(docs):
        (left if i % 2 == 0 else right).append(d)
    return left + right[::-1]


# --- simple whitespace/regex tokenizer
_TOKEN_SPLIT = re.compile(r"[^\w]+", flags=re.UNICODE)

def _tok(text: str) -> list[str]:
    return [t for t in _TOKEN_SPLIT.split(text.lower()) if t]

# Optional tiny cache so we don't rebuild BM25 every call
_BM25_CACHE = {"size": -1, "bm25": None, "docs": None, "tokens": None}

def _get_bm25(all_docs) -> tuple[BM25Okapi, list, list[list[str]]]:
    docs_list = list(all_docs)
    if _BM25_CACHE["size"] == len(docs_list) and _BM25_CACHE["bm25"] is not None:
        return _BM25_CACHE["bm25"], _BM25_CACHE["docs"], _BM25_CACHE["tokens"]

    tokens = [_tok(d.page_content) for d in docs_list]
    bm25 = BM25Okapi(tokens)

    _BM25_CACHE.update({"size": len(docs_list), "bm25": bm25, "docs": docs_list, "tokens": tokens})
    return bm25, docs_list, tokens


# Initialize acronym expander
#expander = AcronymExpander()

def expand_query(query: str, corpus: List[str], top_n: int = 5, expand_acronyms: bool = True, expand_tfidf: bool = True) -> str:
    """
    Multi-purpose query expander:
    - Expands acronyms (e.g., RAG -> Retrieval-Augmented Generation)
    - Pseudo-relevance feedback using TF-IDF
    """
    # 1) Acronym expansion (optional)
    """
    query = expander.expand(query)
    print(f"[DEBUG] After acronym expansion: {query}") 
    """

    # 2) TF-IDF / PRF expansion
    if expand_tfidf and corpus:
        vectorizer = TfidfVectorizer(stop_words='english')
        X = vectorizer.fit_transform(corpus)
        feature_names = vectorizer.get_feature_names_out()

        tfidf_sums = X.sum(axis=0).A1
        top_indices = tfidf_sums.argsort()[::-1][:top_n]
        top_terms = [feature_names[i] for i in top_indices]

        if top_terms:
            query += " " + " ".join(top_terms)
            print(f"[DEBUG] After TF-IDF expansion: {query}")

    return query


# ---------- Dense + BM25 candidate fetchers & fusion ----------
def fetch_candidates(
    vectorstore: FAISS,
    query: str,
    fetch_k: int = 40,
    min_similarity: float = 0.0,  # >=0 keeps only positive cosine similarity
) -> Tuple[List, List[float]]:
    """
    Dense candidates from FAISS, returning (docs, scores).
    Filters out results with similarity < min_similarity.
    """
    pairs = vectorstore.similarity_search_with_relevance_scores(query, k=fetch_k)
    print(f"[DEBUG] Retrieved {len(pairs)} dense candidates for query='{query}'")

    docs, scores = [], []
    for d, s in pairs:
        s = float(s)
        if s >= min_similarity:
            docs.append(d)
            scores.append(s)
            print(scores)

    print(f"[DEBUG] After threshold filter (min_similarity={min_similarity}): kept={len(docs)}")
    return docs, scores


def fetch_bm25_candidates_query(
    query: str,
    bm25: BM25Okapi,
    docs_list: List,
    k: int = 40,
    eps: float = 1e-9
) -> Tuple[List, List[float]]:
    q_tokens = _tok(query)
    scores = bm25.get_scores(q_tokens)  # shape: [num_docs]
    order = np.argsort(scores)[::-1]    # best → worst

    # keep only passages with real lexical match (score > eps)
    nonzero = order[scores[order] > eps]
    k_eff = min(k, len(nonzero))        # don't exceed available nonzero hits
    idx = nonzero[:k_eff]

    out_docs = [docs_list[i] for i in idx]
    out_scores = [float(scores[i]) for i in idx]

    # richer debug so you see what’s happening
    max_s = float(scores[order[0]]) if len(order) else 0.0
    print(f"[DEBUG] BM25: total={len(docs_list)} nonzero={len(nonzero)} "
          f"returned={k_eff} requested_k={k} max_score={max_s:.4f}")
    return out_docs, out_scores



def _minmax(xs: List[float]) -> List[float]:
    if not xs:
        return xs
    lo, hi = min(xs), max(xs)
    rng = hi - lo
    if rng <= 1e-12:
        return [0.0 for _ in xs]
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
        return (d.metadata.get("source"), d.metadata.get("page"), hash(d.page_content))

    table = {}
    for d, s in zip(dense_docs, dense_norm):
        k = key(d)
        table.setdefault(k, {"doc": d, "dense": 0.0, "bm25": 0.0})
        table[k]["dense"] = max(table[k]["dense"], s)

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
        # numerically stable sigmoid
        if x >= 0:
            z = math.exp(-x)
            return 1.0 / (1.0 + z)
        else:
            z = math.exp(x)
            return z / (1.0 + z)
    except OverflowError:
        return 0.0 if x < 0 else 1.0

def rerank_with_ce(
    query: str,
    docs: List,
    *,
    min_score: float = 0.35,       # threshold AFTER normalization (if enabled)
    normalize: bool = True,        # sigmoid → 0–1
    top_k: int | None = None,      # keep only the best K after threshold
    top_n_debug: int = 5
) -> Tuple[List, List[float]]:
    """
    Rerank with BGE cross-encoder from loader.py and apply a score threshold.
    - If normalize=True, raw logits -> sigmoid in [0,1] (recommended for thresholding).
    - Filters out docs with score < min_score.
    - Optionally trims to top_k.
    """
    if not docs:
        return [], []

    ce = get_cross_encoder()  # should return a sentence_transformers.CrossEncoder
    pairs = [(query, d.page_content) for d in docs]
    raw_scores = ce.predict(pairs)  # numpy array (logits)

    # normalize if desired
    if normalize:
        scores = [_sigmoid(float(s)) for s in raw_scores]
    else:
        scores = [float(s) for s in raw_scores]

    # sort desc by score
    ranked = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)

    # threshold filter
    if min_score is not None:
        ranked = [(d, s) for (d, s) in ranked if s >= min_score]

    # optional top-k
    if top_k is not None:
        ranked = ranked[:top_k]

    ranked_docs, ranked_scores = (list(x) for x in zip(*ranked)) if ranked else ([], [])

    # debug
    print(f"[DEBUG] CE total_in={len(docs)} kept={len(ranked_docs)} "
          f"min_score={min_score} normalize={normalize} top_k={top_k}")
    for i, (doc, score) in enumerate(zip(ranked_docs[:top_n_debug], ranked_scores[:top_n_debug])):
        snippet = doc.page_content[:80].replace("\n", " ")
        print(f"[DEBUG] CE score={score:.4f} | Doc {i}: {snippet}...")

    return ranked_docs, ranked_scores


# ---------- Main search ----------

def search_vectorstore(
    query: str,
    index_dir: str,
    k: int = 10,
    fetch_k: int = 40,
    min_ce_score: float = 0.0,        # optional threshold (use with calibration only)
    allow_unsafe: bool = False,
    expand: bool = False,             # optional expansion flag
    expansion_top_n: int = 3,
    use_hybrid: bool = True,          # <-- NEW: turn hybrid on/off
    alpha_dense: float = 0.6,         # <-- NEW: fusion weight for dense
    bm25_k: int = 40                  # <-- NEW: how many BM25 candidates
) -> Tuple[str, List[Tuple[str, str]]]:
    """
    Hybrid retrieval:
      Dense (fetch_k) + BM25 (bm25_k) -> fuse -> Cross-encoder re-rank -> context + sources.
    Set min_ce_score to drop weak results ONLY if you calibrated CE scores.
    """
    vectorstore = get_vectorstore(allow_unsafe=True)
    all_docs = vectorstore.docstore._dict.values()

    # --- Optional query expansion (applies to both dense & BM25) ---
    if expand:
        corpus = [d.page_content for d in all_docs]  # can sample for speed
        query = expand_query(query, corpus, top_n=expansion_top_n)
        print(f"[DEBUG] Expanded Query: {query}")

    # --- Build BM25 (cached) if hybrid ---
    if use_hybrid:
        bm25, docs_list, _ = _get_bm25(all_docs)

    # 1) Recall stage
    dense_docs, dense_scores = fetch_candidates(vectorstore, query, fetch_k=fetch_k)

    if use_hybrid:
        bm25_docs, bm25_scores = fetch_bm25_candidates_query(query, bm25, docs_list, k=bm25_k)
        candidates = fuse_candidates(dense_docs, dense_scores, bm25_docs, bm25_scores, alpha=alpha_dense)
    else:
        candidates = dense_docs

    # 2) Precision stage (CE rerank)
    ranked_docs, ranked_scores = rerank_with_ce(query, candidates)

    # 3) Optional CE threshold (fix: use != and guard)
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
    # Apply bookend reordering
    docs = _bookend(docs)
    print(f"[DEBUG] Returning {len(docs)} final docs (top-k={k})")

    # 5) Outputs
    context = "\n\n".join(d.page_content.strip() for d in docs)
    sources = [(d.metadata.get("source", "unknown"), d.metadata.get("page", "?")) for d in docs]

    seen = set()
    sources = []
    for d in docs:
        key = (d.metadata.get("source", "unknown"), d.metadata.get("page", "?"))
        if key not in seen:
            seen.add(key)
            sources.append(key)

    print("\n[DEBUG] Final Context Preview:\n", context, "\n\n")

    print("[DEBUG] Sources:", sources)

    return context, sources
