# retriever.py
import json
import re
import math
import hashlib
import time
import datetime
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any # Added Dict, Any
from unicodedata import normalize as _unicode_normalize

# --- External Libs ---
from langchain_community.vectorstores import FAISS
from sklearn.feature_extraction.text import TfidfVectorizer
from rank_bm25 import BM25Okapi
import numpy as np
from together import Together  # <--- NEW: For internal routing
from app.services.llm_service import _classify_query_intent  # <--- NEW: Import the intent classifier

# --- Local Imports ---
from .loaders import get_vectorstore, get_cross_encoder

# --- CONFIGURATION ---
# Initialize internal client for routing (Uses the same key)


def _extract_page_constraints(query: str) -> Optional[tuple | int]:
    """
    Returns an int (single page) or tuple (start, end) if pages are mentioned.
    """
    # Pattern 1: Range "pages 10-15"
    range_match = re.search(r"\bpages?\s+(\d+)\s*(?:-|to)\s*(\d+)\b", query, re.IGNORECASE)
    if range_match:
        return (int(range_match.group(1)), int(range_match.group(2)))

    # Pattern 2: Single "page 10"
    single_match = re.search(r"\bpages?\s+(\d+)\b", query, re.IGNORECASE)
    if single_match:
        return int(single_match.group(1))
        
    return None

# --- HELPER 4: JSONL Page Reader (Direct Access) ---
# --- HELPER 4: JSONL Page Reader (Direct Access) ---
def get_specific_pages_from_jsonl(filename: str, pages: tuple | int) -> Optional[str]:
    """
    Reads the JSONL file and extracts ALL chunks that match the specific page(s).
    """
    base_dir = Path("data_store")
    jsonl_path = base_dir / "chunked_output" / f"{Path(filename).stem}_chunks.jsonl"
    
    if not jsonl_path.exists():
        return None

    matching_chunks = []
    
    try:
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                data = json.loads(line)
                chunk_page = data['metadata'].get('page', 0)
                
                # Check match
                is_match = False
                if isinstance(pages, int):
                    if chunk_page == pages: is_match = True
                elif isinstance(pages, tuple):
                    if pages[0] <= chunk_page <= pages[1]: is_match = True
                
                if is_match:
                    matching_chunks.append(data)
    except Exception as e:
        print(f"[ERROR] JSONL Read Error: {e}")
        return None

    if not matching_chunks:
        return None

    # Sort chunks to ensure natural reading order
    matching_chunks.sort(key=lambda x: x['metadata'].get('chunk_index', 0))

    # --- FORMATTING FIX ---
    # We build a list of parts, similar to the main search_vectorstore loop
    context_parts = []
    for idx, c in enumerate(matching_chunks, 1):
        pg = c['metadata'].get('page', '?')
        chunk_content = c['content'].strip()
        
        # EXACT MATCH of the vector search format:
        structured = f"[{idx}] Source: {filename}, Page: {pg}\nContent: {chunk_content}"
        context_parts.append(structured)
        
    return "\n\n".join(context_parts)

# --- HELPER 2: JSONL Reader (Global Context) ---
def get_global_context_from_jsonl(filename: str) -> Optional[str]:
    """
    Retrieves Introduction (First 3 pages) and Conclusion (Last 3 pages) 
    by reading the _chunks.jsonl file directly.
    """
    base_dir = Path("data_store")
    jsonl_path = base_dir / "chunked_output" / f"{Path(filename).stem}_chunks.jsonl"
    
    if not jsonl_path.exists():
        print(f"[DEBUG] JSONL not found at {jsonl_path}")
        return None

    all_chunks = []
    try:
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                all_chunks.append(json.loads(line))
    except Exception:
        return None

    if not all_chunks:
        return None

    # Sort chunks by page
    all_chunks.sort(key=lambda x: x['metadata'].get('page', 0))
    max_page = all_chunks[-1]['metadata'].get('page', 0)
    
    # Grab Intro & Outro
    intro_chunks = [c['content'] for c in all_chunks if c['metadata'].get('page', 0) <= 3]
    outro_chunks = [c['content'] for c in all_chunks if c['metadata'].get('page', 0) >= (max_page - 2)]
    
    # Deduplicate if doc is short
    if max_page <= 6:
         outro_chunks = []

    context = "--- DOCUMENT INTRODUCTION (Pages 1-3) ---\n"
    context += "\n".join(intro_chunks)
    context += "\n\n--- DOCUMENT CONCLUSION (Last 3 Pages) ---\n"
    context += "\n".join(outro_chunks)
    
    return context

# --- Context shaping helpers (Unchanged) ---

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

def remove_stopwords(query: str) -> str:
    query_tokens = query.split()
    query_without_stopwords = [word for word in query_tokens if word.lower() not in ENGLISH_STOP_WORDS]
    return " ".join(query_without_stopwords)

def _bookend(docs):
    left, right = [], []
    for i, d in enumerate(docs):
        (left if i % 2 == 0 else right).append(d)
    return left + right[::-1]

_TOKEN_SPLIT = re.compile(r"[^\w]+", flags=re.UNICODE)

def _tok(text: str) -> list[str]:
    txt = _unicode_normalize("NFKC", text or "")
    return [t for t in _TOKEN_SPLIT.split(txt.lower()) if t]

_BM25_CACHE = { "hash": None, "bm25": None, "docs": None, "tokens": None }

def _docs_hash(docs_list: List) -> str:
    h = hashlib.sha1()
    for d in docs_list:
        meta = d.metadata.get("source", "") + "|" + str(d.metadata.get("page", ""))
        h.update(meta.encode("utf-8"))
        h.update(d.page_content.encode('utf-8'))
    return h.hexdigest()

def _get_bm25(all_docs) -> tuple[Optional[BM25Okapi], list, list[list[str]]]:
    docs_list = list(all_docs)
    if not docs_list:
        return None, [], []

    cur_hash = _docs_hash(docs_list) if docs_list else None
    if _BM25_CACHE["hash"] == cur_hash and _BM25_CACHE["bm25"] is not None:
        return _BM25_CACHE["bm25"], _BM25_CACHE["docs"], _BM25_CACHE["tokens"]

    tokens = [_tok(d.page_content) for d in docs_list]
    bm25 = BM25Okapi(tokens)

    _BM25_CACHE.update({"hash": cur_hash, "bm25": bm25, "docs": docs_list, "tokens": tokens})
    return bm25, docs_list, tokens

# ---------- Dense + BM25 candidate fetchers & fusion ----------
def fetch_candidates(vectorstore: FAISS, query: str, fetch_k: int = 10, min_similarity: Optional[float] = None, filter: Optional[Dict[str, Any]] = None) -> Tuple[List, List[float]]:
    if len(vectorstore.docstore._dict) == 0:
        return [], []

    pairs = vectorstore.similarity_search_with_relevance_scores(
        query, 
        k=fetch_k,
        filter=filter  # <--- PASSED TO NATIVE SEARCH
    )
    print(f"[DEBUG] Raw Dense Retrieval count: {len(pairs)}")
    print(f"[DEBUG] Raw Dense Retrieval count: {len(pairs)}")

    docs, scores = [], []
    for i, (d, s) in enumerate(pairs, 1):
        if (min_similarity is None) or (s >= min_similarity):
            docs.append(d)
            scores.append(s)
    
    return docs, scores

def fetch_bm25_candidates_query(query: str, bm25: BM25Okapi, docs_list: List, k: int = 10, eps: float = 1e-9) -> Tuple[List, List[float]]:
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
    return out_docs, out_scores

def _minmax(xs: List[float]) -> List[float]:
    if not xs: return xs
    lo, hi = min(xs), max(xs)
    rng = hi - lo
    if rng <= 1e-6:
        m = max(abs(x) for x in xs) or 1.0
        return [x / m for x in xs]
    return [(x - lo) / rng for x in xs]

def fuse_candidates(dense_docs: List, dense_scores: List[float], bm25_docs: List, bm25_scores: List[float], alpha: float = 0.5) -> List:
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
    return [d for d, _ in fused]

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

def rerank_with_ce(query: str, docs: List, *, min_score: float = 0.0, normalize: bool = True, top_k: int | None = None, top_n_debug: int = 5) -> Tuple[List, List[float]]:
    if not docs: return [], []
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
    return ranked_docs, ranked_scores


# ---------- Main search ----------

async def search_vectorstore(
    query: str,
    index_dir: str,
    k: int = 10,       # Default fallback
    fetch_k: int = 20, # Default fallback
    min_ce_score: float = 0.0,
    allow_unsafe: bool = False,
    expansion_top_n: int = 3,
    use_hybrid: bool = True,
    alpha_dense: float = 0.5,
    mode: str = "fast", 
    bm25_k: int = 20,
    source: Optional[str] = None,
    query_type: str = "SPECIFIC_SEARCH",
    should_strip_stopwords: bool = False,
) -> Tuple[str, List[Tuple[str, str]]]:

    vectorstore = get_vectorstore(allow_unsafe=True)
    
    # 1. Safety Check: Empty Index
    total_docs = len(vectorstore.docstore._dict)
    if total_docs == 0:
         print("[DEBUG] Index is empty. Returning no context.")
         return "System: No documents available in the database.", []

    # === STEP 1: ADAPTIVE ROUTING (The "Brain") ===
    
    intent = "SPECIFIC_SEARCH" # Default intent
    
    # FIX 1: Allow "precise" mode to trigger the Router
    if mode in ["adaptive", "precise"]:
        print(f"\n[RETRIEVER] 🧠 Analyzing intent for: '{query}' (Mode: {mode})")
        intent = _classify_query_intent(query)
        print(f"[RETRIEVER] 🎯 Intent Detected: {intent}")

                
        # STRATEGY A: Global Summary (JSONL Bypass)
        if intent == "GLOBAL_SUMMARY" and source:
            global_context = get_global_context_from_jsonl(source)
            if global_context:
                print(f"[RETRIEVER] 📚 Returning Global Context (JSONL bypass).")
                return global_context, []
            else:
                print(f"[RETRIEVER] ⚠️ JSONL failed. Falling back to Broad Search.")
                intent = "BROAD_SEARCH"
        elif intent == "PAGE_SPECIFIC" and source:
            target_pages = _extract_page_constraints(query)
            
            if target_pages:
                print(f"[RETRIEVER] 📖 Reading Pages: {target_pages}")
                page_context = get_specific_pages_from_jsonl(source, target_pages)
                
                if page_context:
                    return page_context, [] # <--- EJECT BUTTON (Success)
                else:
                    print("[WARN] Pages not found in JSONL. Falling back to Vector Search.")
            else:
                print("[WARN] 'Page' intent detected but no numbers found. Fallback.")
        
        if intent == "OUT_OF_SCOPE":
            print("[RETRIEVER] 🌀 Out of Scope detected. Skipping retrieval.")   
            return "", []

        if intent == "NONSENSE":
            print("[RETRIEVER] 🌀 Nonsense detected. Skipping retrieval.")
            return "", []

        if intent == "GREETING":
            print("[RETRIEVER] 💬 Greeting detected. Skipping retrieval.")
            # Return EMPTY context. This tells the Generator to just chat normally.
            return "", []
        

        # STRATEGY B: Broad Search (Wide Net)
        if intent == "BROAD_SEARCH":
            k = 30 
            bm25_k = k        
            fetch_k = 60     
            use_hybrid = True
            alpha_dense = 0.7
            
        # STRATEGY C: Specific Search (Sniper)
        elif intent == "SPECIFIC_SEARCH":
            k = 5     
            bm25_k = k         
            fetch_k = 15
            use_hybrid = True
            alpha_dense = 0.3

    # =========================================================

    all_docs = list(vectorstore.docstore._dict.values())

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
    
    # FIX 2: The "Source Filtering" Bug Fix
    # If we are looking for 1 specific file, we need to fetch MANY chunks (e.g. 100) 
    # because the top 20 might be dominated by other files.
    search_filter = {"source": source} if source else None
    dense_docs, dense_scores = fetch_candidates(
        vectorstore, 
        query_to_use, 
        fetch_k=fetch_k, 
        filter=search_filter  # <--- Passing the filter here
    )

  

    # 4. Fusion
    if use_hybrid and bm25_docs:
        candidates = fuse_candidates(dense_docs, dense_scores, bm25_docs, bm25_scores, alpha=alpha_dense)
    else:
        candidates = dense_docs

    # 5. Reranking
    # We trigger reranking if:
    # A) The intent is BROAD (we have 30+ docs, need to sort them)
    # B) The mode is "precise" (User explicitly asked for quality)
    if intent == "BROAD_SEARCH" or mode in ["precise", "adaptive"]:
        ranked_docs, ranked_scores = rerank_with_ce(query_to_use, candidates, top_k=k)
    else:
        # Fast mode: Just slice the list
        print("[DEBUG] Skipping Reranker (Fast Mode)")
        ranked_docs = candidates[:k] 

    # 6. Final Selection
    docs = ranked_docs
    
    # If Broad Search, sort by Page Number to make the reading flow logical
    if intent == "BROAD_SEARCH":
        docs.sort(key=lambda x: x.metadata.get("page", 0))
    elif len(docs) >= 3:
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
    print(intent)
    return context, []