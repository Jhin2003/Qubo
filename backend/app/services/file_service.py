import os
import json
import hashlib
from datetime import datetime
from pathlib import Path

import pytesseract

import fitz  # This is the Python binding for PyMuPDF
from PIL import Image

from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import FAISS

import pdfplumber
# Specify the path to Tesseract (if necessary)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

from langchain_experimental.text_splitter import SemanticChunker

from .loaders import (
    get_embedder,
    get_vectorstore,
)


 # --- Embedding model ---
embedding_model = get_embedder()



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


def extract_images(pdf_path, page_num,  output_dir: str = "extracted_images"):
   
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    saved = []

    page_index = page_num - 1  # fitz is 0-based

    with fitz.open(pdf_path) as doc:
        images = doc.get_page_images(page_index, full=True)
        for i, img in enumerate(images, start=1):
            xref = img[0]
            base = doc.extract_image(xref)
            img_bytes = base["image"]
            ext = base.get("ext", "png")  # e.g., 'png', 'jpeg', 'jbig2', etc.

            path = out / f"page_{page_num}-image_{i}.{ext}"
            with open(path, "wb") as f:
                f.write(img_bytes)
            saved.append(str(path))

    print(f"[DEBUG] Page {page_num}: saved {len(saved)} image(s) to {out}")
    return saved  
 

import io

def ocr_page_embedded_images(doc: fitz.Document, page_index_zero_based: int) -> list[str]:
    """
    OCR all embedded raster images on a page (0-based) and return a list of non-empty texts.
    """
    texts = []
    images = doc.get_page_images(page_index_zero_based, full=True)
    for _, (xref, *_) in enumerate(images, start=1):
        base = doc.extract_image(xref)
        img_bytes = base["image"]

        img = Image.open(io.BytesIO(img_bytes)).convert("L")
        img = img.point(lambda px: 255 if px > 200 else 0)  # simple binarize
        t = pytesseract.image_to_string(img, config="--psm 6").strip()
        if t:
            texts.append(t)
    return texts


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
    # --- Extract text per page ---
    with pdfplumber.open(pdf_path) as pdf, fitz.open(pdf_path) as fdoc:
        page_texts = []
        for page_num, page in enumerate(pdf.pages, start=1):
            # 1) selectable text
            text = page.extract_text(x_tolerance=1, y_tolerance=2) or ""
            if text.strip():
                page_texts.append((page_num, text))

            # 2) embedded images → OCR in-memory (no saving)
            if page.images or len(fdoc.get_page_images(page_num - 1, full=True)) > 0:
                ocr_texts = ocr_page_embedded_images(fdoc, page_num - 1)
                for t in ocr_texts:
                    page_texts.append((page_num, t))

    # --- Split text into chunks ---
    chunker = SemanticChunker(
        embeddings=embedding_model,
        breakpoint_threshold_type="percentile",
        breakpoint_threshold_amount=95,
        buffer_size=1,
        min_chunk_size=200,
       
    )

    chunks_with_pages = []
    for page_num, page_text in page_texts:
        page_chunks = chunker.split_text(page_text)
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

   

    # --- Check if FAISS index exists (both files must exist) ---
    index_file = index_dir / "index.faiss"
    store_file = index_dir / "index.pkl"

    if index_file.exists() and store_file.exists():
        print(f"Loading existing FAISS index from '{index_dir}'")
        vectorstore = get_vectorstore(allow_unsafe=True)
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

