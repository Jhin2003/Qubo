#!/usr/bin/env python3
import argparse
import faiss
import json
import os
import sys
import pickle
from typing import List, Dict, Any
from tqdm import tqdm
import numpy as np

try:
    from sentence_transformers import SentenceTransformer
except Exception as e:
    print("ERROR: sentence-transformers is required. Install with: pip install sentence-transformers", file=sys.stderr)
    raise

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

def load_chunks(path: str) -> List[Dict[str, Any]]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows

def normalize_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Ensure required fields exist
    out = []
    for r in rows:
        rid = r.get("id") or ""
        text = r.get("text") or ""
        meta = r.get("metadata") or {}
        out.append({"id": rid, "text": text, "metadata": meta})
    return out

def embed_texts(model: SentenceTransformer, texts: List[str], batch_size: int = 64) -> np.ndarray:
    embs = model.encode(texts, batch_size=batch_size, show_progress_bar=True, convert_to_numpy=True, normalize_embeddings=True)
    return embs.astype("float32")

def build_index(chunks_path: str, out_dir: str):
    os.makedirs(out_dir, exist_ok=True)
    rows = normalize_rows(load_chunks(chunks_path))
    texts = [r["text"] for r in rows]
    print(f"Loaded {len(texts)} chunks")

    model = SentenceTransformer(MODEL_NAME)
    vecs = embed_texts(model, texts)

    d = vecs.shape[1]
    index = faiss.IndexFlatIP(d)  # inner product (cosine since normalized)
    index.add(vecs)
    faiss.write_index(index, os.path.join(out_dir, "index.faiss"))
    with open(os.path.join(out_dir, "meta.jsonl"), "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(os.path.join(out_dir, "model.txt"), "w", encoding="utf-8") as f:
        f.write(MODEL_NAME)

    print(f"Saved index to {os.path.join(out_dir, 'index.faiss')}")
    print(f"Saved metadata to {os.path.join(out_dir, 'meta.jsonl')}")
    print(f"Model used: {MODEL_NAME}")

def load_index(index_dir: str):
    index_path = os.path.join(index_dir, "index.faiss")
    meta_path = os.path.join(index_dir, "meta.jsonl")
    model_path = os.path.join(index_dir, "model.txt")
    if not (os.path.exists(index_path) and os.path.exists(meta_path)):
        print("ERROR: index.faiss or meta.jsonl not found in the index directory.", file=sys.stderr)
        sys.exit(2)
    index = faiss.read_index(index_path)
    rows = []
    with open(meta_path, "r", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    model_name = MODEL_NAME
    if os.path.exists(model_path):
        with open(model_path, "r", encoding="utf-8") as f:
            model_name = f.read().strip() or MODEL_NAME
    model = SentenceTransformer(model_name)
    return index, rows, model

def search(index_dir: str, query: str, topk: int = 5):
    index, rows, model = load_index(index_dir)
    q_emb = embed_texts(model, [query])
    D, I = index.search(q_emb, topk)
    hits = []
    for rank, idx in enumerate(I[0]):
        if idx < 0 or idx >= len(rows):
            continue
        r = rows[idx]
        hits.append({
            "rank": rank + 1,
            "score": float(D[0][rank]),
            "id": r.get("id"),
            "text": r.get("text"),
            "metadata": r.get("metadata", {}),
        })
    return hits

def main():
    ap = argparse.ArgumentParser(description="Embed chunks.jsonl into FAISS and search them.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ap_build = sub.add_parser("build", help="Build FAISS index from chunks.jsonl")
    ap_build.add_argument("--chunks", required=True, help="Path to chunks.jsonl")
    ap_build.add_argument("--out", required=True, help="Output directory for index files")

    ap_search = sub.add_parser("search", help="Search the FAISS index")
    ap_search.add_argument("--index", required=True, help="Index directory created by 'build'")
    ap_search.add_argument("--query", required=True, help="Natural language query")
    ap_search.add_argument("--topk", type=int, default=5, help="Number of hits to return")

    args = ap.parse_args()

    if args.cmd == "build":
        build_index(args.chunks, args.out)
    elif args.cmd == "search":
        hits = search(args.index, args.query, args.topk)
        for h in hits:
            meta = h.get("metadata", {})
            src = meta.get("source_path", "unknown")
            pg = meta.get("page_start", "?")
            print(f"[{h['rank']}] score={h['score']:.3f} page={pg} src={src}")
            print(h["text"].strip())
            print("-" * 80)

if __name__ == "__main__":
    main()
