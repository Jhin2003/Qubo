# retriever.py
from pathlib import Path
from typing import List, Tuple, Optional
import re
import math
import hashlib
from unicodedata import normalize as _unicode_normalize

from langchain_community.vectorstores import FAISS
from sklearn.feature_extraction.text import TfidfVectorizer

from rank_bm25 import BM25Okapi
import numpy as np

from .loaders import get_vectorstore, get_cross_encoder, get_complexity_classifier

# --- Context shaping helpers ---

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

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
        meta = d.metadata.get("source", "") + "|" + str(d.metadata.get("page", ""))
        h.update(meta.encode("utf-8"))
        h.update(d.page_content.encode('utf-8'))
    return h.hexdigest()

def _get_bm25(all_docs) -> tuple[Optional[BM25Okapi], list, list[list[str]]]:
    docs_list = list(all_docs)

    # === FIX 1: Prevent Division by Zero on Empty Docs ===
    if not docs_list:
        return None, [], []
    # =====================================================

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
    fetch_k: int = 10,
    min_similarity: Optional[float] = None,
) -> Tuple[List, List[float]]:
    """Dense candidates from FAISS with Debug Logging."""
    
    # Check if store is empty
    if len(vectorstore.docstore._dict) == 0:
        print("[DEBUG] Vectorstore empty, returning no candidates.")
        return [], []

    # Get (Document, Score) pairs
    # Since we used DistanceStrategy.COSINE, 's' is already Cosine Similarity.
    pairs = vectorstore.similarity_search_with_relevance_scores(query, k=fetch_k)
    print(f"[DEBUG] Raw Dense Retrieval count: {len(pairs)}")

    docs, scores = [], []
    
    print(f"\n--- [DENSE CANDIDATES LOG] Query: '{query}' ---")
    for i, (d, s) in enumerate(pairs, 1):
        # Snippet for logging (first 50 chars)
        snippet = d.page_content.replace('\n', ' ')[:50] + "..."
        src = d.metadata.get("source", "unknown")
        pg = d.metadata.get("page", "?")
        
        # Log every candidate to inspect the score range
        print(f"   {i}. Score: {s:.4f} | {src} (p{pg}) | \"{snippet}\"")

        # Threshold check
        if (min_similarity is None) or (s >= min_similarity):
            docs.append(d)
            scores.append(s)
        else:
            print(f"      [DROPPED] Below threshold {min_similarity}")

    print(f"--- End Log (Kept {len(docs)}) ---\n")
    
    return docs, scores


def fetch_bm25_candidates_query(
    query: str,
    bm25: BM25Okapi,
    docs_list: List,
    k: int = 10,
    eps: float = 1e-9,
) -> Tuple[List, List[float]]:
    """Return top-k BM25 hits."""
    # Safety check if BM25 didn't initialize
    if bm25 is None:
        return [], []

    q_tokens = _tok(query)
    scores = bm25.get_scores(q_tokens)
    order = np.argsort(scores)[::-1]

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
    if rng <= 1e-6:
        m = max(abs(x) for x in xs) or 1.0
        return [x / m for x in xs]
    return [(x - lo) / rng for x in xs]


def fuse_candidates(
    dense_docs: List, dense_scores: List[float],
    bm25_docs: List, bm25_scores: List[float],
    alpha: float = 0.5
) -> List:
    dense_norm = _minmax(dense_scores)
    bm25_norm = _minmax(bm25_scores)

    def key(d):
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
    if not docs:
        return [], []

    if _CE_MODEL["model"] is None:
        _CE_MODEL["model"] = get_cross_encoder()
    ce = _CE_MODEL["model"]

    pairs = [(query, d.page_content) for d in docs]
    raw_scores = _ce_predict_batched(ce, pairs, batch_size=64)

    if normalize:
        scores = [_sigmoid(float(s)) for s in raw_scores]
    else:
        scores = [float(s) for s in raw_scores]

    ranked = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)

    if min_score is not None:
        ranked = [(d, s) for (d, s) in ranked if s >= min_score]

    if top_k is not None:
        ranked = ranked[:top_k]

    ranked_docs, ranked_scores = (list(x) for x in zip(*ranked)) if ranked else ([], [])

    print(f"[DEBUG] CE total_in={len(docs)} kept={len(ranked_docs)} min_score={min_score} normalize={normalize} top_k={top_k}")
    return ranked_docs, ranked_scores


# ---------- Main search ----------

async def search_vectorstore(
    query: str,
    index_dir: str,
    k: int = 10,
    fetch_k: int = 20,
    min_ce_score: float = 0.0,
    allow_unsafe: bool = False,
    expansion_top_n: int = 3,
    use_hybrid: bool = True,
    alpha_dense: float = 0.5,
    mode: str = "fast", 
    bm25_k: int = 20,
    source: Optional[str] = None,
    should_strip_stopwords: bool = False,
) -> Tuple[str, List[Tuple[str, str]]]:

    vectorstore = get_vectorstore(allow_unsafe=True)

    # 1. Safety Check: Empty Index
    total_docs = len(vectorstore.docstore._dict)
    if total_docs == 0:
         print("[DEBUG] Index is empty. Returning no context.")
         return "System: No documents available in the database.", []

    all_docs = list(vectorstore.docstore._dict.values())
    
    # --- LOGIC BRANCHING ---
    # We set default behaviors here, then override based on mode
    should_rerank = True 

    if mode == "fast":
        # === FAST MODE: Hybrid YES, Rerank NO ===
        print(f"[MODE] FAST: Hybrid Search enabled. Skipping Classifier & Reranker for speed.")
        
        # Fixed settings (No classifier latency)
        fetch_k = 10       
        bm25_k = 10
        k = 5              
        
        use_hybrid = True     # <--- Kept Hybrid as requested
        should_rerank = False # <--- Turned off Reranker
        
    elif mode == "precise":
        # === PRECISE ADAPTIVE: Quality Floor Enforced ===
        print(f"[MODE] PRECISE: Analyzing complexity to scale 'k' (Hybrid+Rerank Enforced)...")
        
        classifier = get_complexity_classifier()
        query_complexity = classifier(query)
        best_result = max(query_complexity, key=lambda x: x['score'])
        predicted_label = best_result['label']

        # ALWAYS True for Precise Mode
        use_hybrid = True  
        should_rerank = True 

        if predicted_label == 'LABEL_0': # Simple
            print("[ADAPTIVE-PRECISE] Easy Query: Lower 'k', but maintaining Hybrid+Rerank.")
            fetch_k, bm25_k, k = 15, 15, 5
            min_ce_score = 0.4             

        elif predicted_label == 'LABEL_1': # Medium
            print("[ADAPTIVE-PRECISE] Medium Query: Standard Hybrid RAG.")
            fetch_k, bm25_k, k = 20, 20, 5
            min_ce_score = 0.4

        elif predicted_label == 'LABEL_2': # Complex
            print("[ADAPTIVE-PRECISE] Hard Query: Deep Search.")
            fetch_k, bm25_k, k = 30, 30, 10
            alpha_dense, min_ce_score = 0.5, 0.4

    else:
        # === LEGACY ADAPTIVE (Standard/Auto) ===
        print(f"[MODE] AUTO: Fully Adaptive.")
        classifier = get_complexity_classifier()
        query_complexity = classifier(query)
        best_result = max(query_complexity, key=lambda x: x['score'])
        predicted_label = best_result['label']

        if predicted_label == 'LABEL_0':
            fetch_k, bm25_k, k = 10, 10, 3
            use_hybrid, should_rerank = True, False # Auto can drop reranker for easy queries
            min_ce_score = 0.1
        elif predicted_label == 'LABEL_1':
            fetch_k, bm25_k, k = 20, 20, 5
            use_hybrid, should_rerank = True, True
            min_ce_score = 0.1
        elif predicted_label == 'LABEL_2':
            fetch_k, bm25_k, k = 30, 30, 10
            use_hybrid, should_rerank = True, True
            min_ce_score = 0.0

    # -----------------------

    if should_strip_stopwords:
        query_to_use = remove_stopwords(query)
    else:
        query_to_use = query

    # 2. Build BM25 (Only if use_hybrid is True)
    bm25_docs, bm25_scores = [], []
    
    if use_hybrid:
        if source:
            bm25_source_iter = [d for d in all_docs if d.metadata.get("source") == source]
        else:
            bm25_source_iter = all_docs

        bm25, docs_list, _ = _get_bm25(bm25_source_iter)

        if bm25 is None:
            print("[WARN] BM25 failed (no documents found). Skipping BM25.")
        else:
            bm25_docs, bm25_scores = fetch_bm25_candidates_query(query_to_use, bm25, docs_list, k=bm25_k)


    # 3. Dense Retrieval
    dense_docs, dense_scores = fetch_candidates(vectorstore, query_to_use, fetch_k=fetch_k)

    if source:
        filtered = [(d, s) for d, s in zip(dense_docs, dense_scores) if d.metadata.get("source") == source]
        dense_docs = [d for d, _ in filtered]
        dense_scores = [s for _, s in filtered]

    # 4. Fusion
    if use_hybrid and bm25_docs:
        candidates = fuse_candidates(dense_docs, dense_scores, bm25_docs, bm25_scores, alpha=alpha_dense)
    else:
        candidates = dense_docs

    # 5. Reranking
    if should_rerank:
        ranked_docs, ranked_scores = rerank_with_ce(query_to_use, candidates)
        
        # Apply CE Threshold
        if min_ce_score and ranked_docs:
            keep_docs, keep_scores = [], []
            for d, s in zip(ranked_docs, ranked_scores):
                if s >= min_ce_score:
                    keep_docs.append(d)
                    keep_scores.append(s)
            ranked_docs = keep_docs
    else:
        # Fast Mode hits this block
        print("[DEBUG] Skipping Reranker (Score=1.0 placeholders)")
        # We must simply return candidates. 
        # Since 'candidates' is just a list of docs from fuse_candidates, 
        # we treat them as if they are 'ranked' by the fusion score.
        ranked_docs = candidates 

    # 6. Final Selection
    docs = ranked_docs[:k] if ranked_docs else []
    
    # Only bookend if we reranked (because bookending assumes high precision)
    # or if we have enough docs.
    if len(docs) >= 3:
        docs = _bookend(docs)
    
    print(f"[DEBUG] Returning {len(docs)} final docs (top-k={k})")

    context_parts = []
    for idx, d in enumerate(docs, 1):
        src = d.metadata.get("source", "unknown")
        pg = d.metadata.get("page", "?")
        chunk = d.page_content.strip()
        structured = f"[{idx}] Source: {src}, Page: {pg}\nContent: {chunk}"
        context_parts.append(structured)

    context = "\n\n".join(context_parts)
    return context, []