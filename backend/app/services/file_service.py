import os
import json
import hashlib
import io
import tempfile  # <-- Add this for temporary files
from datetime import datetime
from pathlib import Path

# --- Dependencies ---
import pytesseract
import fitz  # PyMuPDF
from PIL import Image
import pdfplumber
import docx2pdf  # <-- Add this for DOCX conversion

# --- LangChain ---
from langchain.vectorstores import FAISS
from langchain_experimental.text_splitter import SemanticChunker

# --- Local Imports ---
from .loaders import get_embedder, get_vectorstore

# --- Configuration ---
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
embedding_model = get_embedder()

# --- Helpers (Unchanged) ---
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

def ocr_page_embedded_images(doc: fitz.Document, page_index_zero_based: int) -> list[str]:
    """OCR all embedded raster images on a page and return a list of non-empty texts."""
    texts = []
    images = doc.get_page_images(page_index_zero_based, full=True)
    for _, (xref, *_) in enumerate(images, start=1):
        base = doc.extract_image(xref)
        img_bytes = base["image"]
        img = Image.open(io.BytesIO(img_bytes)).convert("L")
        img = img.point(lambda px: 255 if px > 200 else 0)
        t = pytesseract.image_to_string(img, config="--psm 6").strip()
        if t:
            texts.append(t)
    return texts

# --- UPDATED: Main Processor ---
def process_file(file_path: str, filename: str):
    """
    Processes a file (PDF or DOCX) into chunks and stores them in FAISS.
    For DOCX, it first converts the file to a temporary PDF.
    Returns: (num_chunks, output_path)
    """
    extension = Path(file_path).suffix.lower()
    processing_path = file_path
    temp_pdf_path = None

    # Use a try...finally block to ensure cleanup of temporary files
    try:
        # --- 1. Handle DOCX conversion if necessary ---
        if extension == '.docx':
            print(f"DOCX file detected. Converting '{filename}' to temporary PDF...")
            # Create a temporary path for the converted PDF
            temp_dir = tempfile.gettempdir()
            temp_pdf_path = os.path.join(temp_dir, f"{Path(filename).stem}.pdf")
            
            # Convert the DOCX to PDF at the temporary path
            docx2pdf.convert(file_path, temp_pdf_path)
            
            # The path to be processed is now the temporary PDF
            processing_path = temp_pdf_path
            print("Conversion complete. Processing temporary PDF.")
        elif extension != '.pdf':
            print(f"Unsupported file type: '{extension}'. Skipping.")
            return 0, None

        # --- 2. Extract text from the PDF (original or temporary) ---
        page_texts = []
        with pdfplumber.open(processing_path) as pdf, fitz.open(processing_path) as fdoc:
            for page_num, page in enumerate(pdf.pages, start=1):
                # Selectable text
                text = page.extract_text(x_tolerance=1, y_tolerance=2) or ""
                if text.strip():
                    page_texts.append((page_num, text))
                # OCR text from images
                if page.images or len(fdoc.get_page_images(page_num - 1, full=True)) > 0:
                    ocr_texts = ocr_page_embedded_images(fdoc, page_num - 1)
                    for t in ocr_texts:
                        page_texts.append((page_num, t))
        
        if not page_texts:
            print(f"No text extracted from '{filename}'. Aborting.")
            return 0, None

        # --- 3. The rest of the pipeline remains the same ---
        base_dir = Path("data_store")
        output_dir = base_dir / "chunked_output"
        index_dir = base_dir / "vector_database"
        output_dir.mkdir(parents=True, exist_ok=True)
        index_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{Path(filename).stem}_chunks.jsonl"

        # --- Split text into chunks ---
        chunker = SemanticChunker(
            embeddings=embedding_model,
            breakpoint_threshold_type="percentile",
            breakpoint_threshold_amount=95,
            min_chunk_size=200,
        )
        chunks_with_pages = []
        for page_num, page_text in page_texts:
            page_chunks = chunker.split_text(page_text)
            for idx, ch in enumerate(page_chunks, start=1):
                chunks_with_pages.append((page_num, idx, ch))
        print(f"Created {len(chunks_with_pages)} chunks for '{filename}'")

        # --- Prepare texts and metadata (using original file for hash) ---
        source_sha1 = sha1_of_file(file_path) # Hash the original file
        created_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        texts = [chunk for _, _, chunk in chunks_with_pages]
        metadatas = [
            {"id": make_chunk_id(source_sha1, p_num, g_idx, p_idx), "source": filename, "page": p_num, "created_at": created_at}
            for g_idx, (p_num, p_idx, _) in enumerate(chunks_with_pages)
        ]

        # --- Add to FAISS and save ---
        index_file = index_dir / "index.faiss"
        store_file = index_dir / "index.pkl"
        if index_file.exists() and store_file.exists():
            print(f"Loading and updating existing FAISS index from '{index_dir}'")
            vectorstore = get_vectorstore(allow_unsafe=True)
            vectorstore.add_texts(texts=texts, metadatas=metadatas)
        else:
            print(f"Creating a new FAISS index at '{index_dir}'")
            vectorstore = FAISS.from_texts(texts=texts, embedding=embedding_model, metadatas=metadatas, normalize_L2=True)
        
        vectorstore.save_local(str(index_dir))

        # --- Save chunks to JSONL ---
        with open(output_path, "w", encoding="utf-8") as f:
            for i, chunk_text in enumerate(texts):
                f.write(json.dumps({"content": chunk_text, "metadata": metadatas[i]}, ensure_ascii=False) + "\n")

        print(f"FAISS index saved/updated at '{index_dir}' with {len(texts)} new documents.")
        return len(chunks_with_pages), output_path

    finally:
        # --- 4. Clean up the temporary PDF file ---
        if temp_pdf_path and os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)
            print(f"Cleaned up temporary file: {temp_pdf_path}")