import os
import json
import hashlib
from datetime import datetime
from pathlib import Path

import pdfplumber
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import FAISS


# --- Helpers ---------------------------------------------------------------
def sha1_of_file(path, buf_size=1024 * 1024):
    """Generate a SHA-1 hash of the file's contents."""
    h = hashlib.sha1()
    with open(path, "rb") as f:
        while True:
            b = f.read(buf_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def make_chunk_id(source_sha1: str, page: int, global_idx: int, page_idx: int) -> str:
    """Generate a unique ID for each chunk."""
    core = f"{source_sha1[:12]}:p{page}:g{global_idx}:k{page_idx}"
    return hashlib.sha1(core.encode("utf-8")).hexdigest()


def process_pdf_chunks(pdf_path: str, output_dir: str, filename: str, index_dir: str):
    """Process the PDF into chunks, generate embeddings, and store them in FAISS."""
    
    # Ensure directories exist
    os.makedirs(output_dir, exist_ok=True)
    Path(index_dir).mkdir(parents=True, exist_ok=True)

    # Output JSONL path
    output_path = os.path.join(output_dir, f"{filename}_chunks.jsonl")

    # --- Extract text per page ---
    with pdfplumber.open(pdf_path) as pdf:
        page_texts = []
        for i, page in enumerate(pdf.pages, start=1):
            txt = page.extract_text() or ""
            if txt.strip():
                page_texts.append((i, txt))

    # --- Split text into chunks ---
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,  # Adjust chunk size for real embeddings
        chunk_overlap=200,
        length_function=len,
    )

    chunks_with_pages = []
    for page_num, page_text in page_texts:
        page_chunks = splitter.split_text(page_text)
        for idx_in_page, ch in enumerate(page_chunks, start=1):
            chunks_with_pages.append((page_num, idx_in_page, ch))

    # --- File-level provenance ---
    source_name = os.path.basename(pdf_path)
    source_sha1 = sha1_of_file(pdf_path)
    created_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    # --- Prepare texts and metadata ---
    texts = [chunk_text for _, _, chunk_text in chunks_with_pages]
    metadatas = [
        {
            "id": make_chunk_id(source_sha1, page_num, global_idx, idx_in_page),
            "source": source_name,
            "page": page_num,
            "author": "Unknown",
            "created_at": created_at,
        }
        for global_idx, (page_num, idx_in_page, _) in enumerate(chunks_with_pages)
    ]

    # --- Embedding model ---
    embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

    # --- Create FAISS vectorstore directly from texts ---
    vectorstore = FAISS.from_texts(
        texts=texts,
        embedding=embedding_model,
        metadatas=metadatas,
        normalize_L2=True
    )

    # --- Save FAISS index ---
    vectorstore.save_local(index_dir)

    # --- Save JSONL ---
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            for global_idx, (page_num, idx_in_page, chunk_text) in enumerate(chunks_with_pages):
                meta = {
                    "content": chunk_text,
                    "metadata": metadatas[global_idx],
                }
                f.write(json.dumps(meta, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"Error writing to file {output_path}: {e}")
        return 0

    print(f"FAISS index saved to '{index_dir}' with {len(texts)} documents (metadata included).")
    return len(chunks_with_pages)
