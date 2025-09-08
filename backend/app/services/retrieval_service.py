# retriever.py
from pathlib import Path
from typing import List, Tuple
import re

from langchain.vectorstores import FAISS
from langchain.embeddings import HuggingFaceEmbeddings

from .loaders import get_vectorstore, get_cross_encoder


def fetch_candidates(vectorstore: FAISS, query: str, fetch_k: int = 40) -> List:
    """Get a larger candidate set to give the cross-encoder room to work."""
    pairs = vectorstore.similarity_search_with_relevance_scores(query, k=fetch_k)
    docs = [d for d, _ in pairs]

    print(f"[DEBUG] Retrieved {len(docs)} candidates from FAISS for query='{query}'")

    # simple dedup by (source, page) to avoid near-duplicates
    seen, uniq = set(), []
    for d in docs:
        key = (d.metadata.get("source"), d.metadata.get("page"))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(d)
    print(f"[DEBUG] After deduplication: {len(uniq)} candidates")
    return uniq


def rerank_with_ce(query: str, docs: List, top_n_debug: int = 5) -> Tuple[List, List[float]]:
    """Sort docs by cross-encoder score (desc) and return scores."""
    if not docs:
        return [], []

    ce = get_cross_encoder()
    scores = ce.predict([(query, d.page_content) for d in docs]).tolist()

    # rank documents by score
    ranked = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
    ranked_docs, ranked_scores = zip(*ranked) if ranked else ([], [])

    # Print the top N reranked scores for inspection
    for i, (doc, score) in enumerate(zip(ranked_docs[:top_n_debug], ranked_scores[:top_n_debug])):
        snippet = doc.page_content[:80].replace("\n", " ")
        print(f"[DEBUG] CE score={score:.4f} | Doc {i}: {snippet}...")

    return list(ranked_docs), list(ranked_scores)


def search_vectorstore(
    query: str,
    index_dir: str,
    k: int = 5,
    fetch_k: int = 40,
    min_ce_score: float = 3.0,
    allow_unsafe: bool = False
) -> Tuple[str, List[Tuple[str, str]]]:
    """
    Dense retrieval (fetch_k) -> Cross-encoder re-rank -> top-k -> context + sources.
    Set min_ce_score to drop weak results and trigger a graceful 'no evidence' path.
    """
    vectorstore = get_vectorstore(allow_unsafe=True)

    # 1) recall
    candidates = fetch_candidates(vectorstore, query, fetch_k=fetch_k)

    # 2) precision (rerank and get scores)
    ranked_docs, ranked_scores = rerank_with_ce(query, candidates)

    # 3) optional thresholding
    if min_ce_score is not None and ranked_docs:
        filtered_docs = [d for d, s in zip(ranked_docs, ranked_scores) if s >= min_ce_score]
        filtered_scores = [s for s in ranked_scores if s >= min_ce_score]
        print(f"[DEBUG] Filtered out {len(ranked_docs) - len(filtered_docs)} docs below CE threshold={min_ce_score}")
        ranked_docs, ranked_scores = filtered_docs, filtered_scores

    # 4) top-k
    docs = ranked_docs[:k] if ranked_docs else []
    print(f"[DEBUG] Returning {len(docs)} final docs (top-k={k})")

    # 5) outputs
    context = "\n\n".join(d.page_content.strip() for d in docs)
    sources = [(d.metadata.get("source", "unknown"), d.metadata.get("page", "?")) for d in docs]

    print("\n[DEBUG] Final Context Preview:\n", context[:300], "...\n")
    print("[DEBUG] Sources:", sources)

    return context, sources
