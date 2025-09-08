import os
import json
import hashlib
from datetime import datetime
from pathlib import Path

import pdfplumber
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import FAISS


from .loaders import (
    get_embedder,
    get_vectorstore,
    # if you have a BM25-only invalidator, prefer that; else use invalidate_all
    # invalidate_bm25_cache, 
   
)


# --- Helpers ---------------------------------------------------------------
def sha1_of_file(path, buf_size=1024 * 1024):
    """Generate a SHA-1 hash of the file's contents."""
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(buf_size), b""):
            h.update(chunk)
    return h.hexdigest()


def make_chunk_id(source_sha1: str, page: int, global_idx: int, page_idx: int) -> str:
    """Generate a unique ID for each chunk."""
    core = f"{source_sha1[:12]}:p{page}:g{global_idx}:k{page_idx}"
    return hashlib.sha1(core.encode("utf-8")).hexdigest()


# --- Main processor --------------------------------------------------------
def process_pdf_chunks(pdf_path: str, filename: str):
    """
    Process the PDF into chunks, generate embeddings, and store them in FAISS.
    Returns: (num_chunks, output_path)
    """

    base_dir = Path("data_store")
    output_dir = base_dir / "chunked_output"
    index_dir = base_dir / "vector_database"

    output_dir.mkdir(parents=True, exist_ok=True)
    index_dir.mkdir(parents=True, exist_ok=True)

    # JSONL output path
    output_path = output_dir / f"{filename}_chunks.jsonl"

    # --- Extract text per page ---
    with pdfplumber.open(pdf_path) as pdf:
        page_texts = []
        for i, page in enumerate(pdf.pages, start=1):
            txt = page.extract_text() or ""
            if txt.strip():
                page_texts.append((i, txt))

    # --- Split text into chunks ---
    splitter = RecursiveCharacterTextSplitter(
    chunk_size=600,          # larger = fewer mid-sentence cuts
    chunk_overlap=100,       # ~80–120 is plenty
    separators=["\n\n","\n",". ","? ","! ","; ",": "," "],
    length_function=len,
    )

    chunks_with_pages = []
    for page_num, page_text in page_texts:
        page_chunks = splitter.split_text(page_text)
        for idx_in_page, ch in enumerate(page_chunks, start=1):
            chunks_with_pages.append((page_num, idx_in_page, ch))
    print(f"{filename}: {len(chunks_with_pages)} chunks")

   

    # --- File-level provenance ---
    source_sha1 = sha1_of_file(pdf_path)
    created_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    # --- Prepare texts and metadata ---
    texts = [chunk_text for _, _, chunk_text in chunks_with_pages]
    metadatas = [
        {
            "id": make_chunk_id(source_sha1, page_num, global_idx, idx_in_page),
            "source": filename,
            "page": page_num,
            "created_at": created_at,
        }
        for global_idx, (page_num, idx_in_page, _) in enumerate(chunks_with_pages)
    ]

    # --- Embedding model ---
    embedding_model = get_embedder()

    # --- Check if FAISS index exists (both files must exist) ---
    index_file = index_dir / "index.faiss"
    store_file = index_dir / "index.pkl"

    if index_file.exists() and store_file.exists():
        print(f"Loading existing FAISS index from '{index_dir}'")
        vectorstore = FAISS.load_local(str(index_dir), embedding_model, allow_dangerous_deserialization=True)
        vectorstore.add_texts(texts=texts, metadatas=metadatas)
    else:
        print(f"Creating a new FAISS index at '{index_dir}'")
        vectorstore = FAISS.from_texts(
            texts=texts,
            embedding=embedding_model,
            metadatas=metadatas,
            normalize_L2=True,
        )

    # --- Add new chunks and save ---
    
    print("uploaded to faiss")
    vectorstore.save_local(str(index_dir))

    # --- Save JSONL ---
    with open(output_path, "w", encoding="utf-8") as f:
        for i, (_, _, chunk_text) in enumerate(chunks_with_pages):
            meta = {"content": chunk_text, "metadata": metadatas[i]}
            f.write(json.dumps(meta, ensure_ascii=False) + "\n")

    print(f"FAISS index saved/updated at '{index_dir}' with {len(texts)} documents.")
    return len(chunks_with_pages), output_path
