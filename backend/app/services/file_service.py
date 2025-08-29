import os
import json
import hashlib
from datetime import datetime



from langchain.text_splitter import RecursiveCharacterTextSplitter

import pdfplumber

# --- Helpers ---------------------------------------------------------------

def sha1_of_file(path, buf_size=1024 * 1024):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        while True:
            b = f.read(buf_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

def make_chunk_id(source_sha1: str, page: int, global_idx: int, page_idx: int) -> str:
    core = f"{source_sha1[:12]}:p{page}:g{global_idx}:k{page_idx}"
    return hashlib.sha1(core.encode("utf-8")).hexdigest()

def process_pdf_chunks(pdf_path: str, output_path: str):
    # Extract per-page text
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        page_texts = []
        for i, page in enumerate(pdf.pages, start=1):
            txt = page.extract_text() or ""
            if txt.strip():
                page_texts.append((i, txt))

    # Splitter (per page to keep page provenance)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=10,
        chunk_overlap=1,
        length_function=len,
    )

    # Build a global list of (page, chunk_text)
    chunks_with_pages = []
    for page_num, page_text in page_texts:
        page_chunks = splitter.split_text(page_text)
        for idx_in_page, ch in enumerate(page_chunks, start=1):
            chunks_with_pages.append((page_num, idx_in_page, ch))

    # File-level provenance
    source_name = os.path.basename(pdf_path)
    source_sha1 = sha1_of_file(pdf_path)
    created_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    # Write JSONL with simplified structure
    with open(output_path, "w", encoding="utf-8") as f:
        for global_idx, (page_num, idx_in_page, chunk_text) in enumerate(chunks_with_pages):
            meta = {
                "content": chunk_text,
                "metadata": {
                    "id": make_chunk_id(source_sha1, page_num, global_idx, idx_in_page),
                    "source": source_name,
                    "page": page_num,
                    "author": "Unknown",  # Add your logic to extract author if available
                    "created_at": created_at,
                },
            }
            f.write(json.dumps(meta, ensure_ascii=False) + "\n")
    
    return len(chunks_with_pages)  # Return the number of chunks processed

