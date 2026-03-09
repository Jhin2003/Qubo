import os
import json
import hashlib
import tempfile
from datetime import datetime
from pathlib import Path
import numpy as np

# --- Dependencies ---
import pdfplumber
import docx2pdf 
from langchain_text_splitters import TokenTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_experimental.text_splitter import SemanticChunker
from langchain_community.vectorstores.utils import DistanceStrategy

# --- Local Imports ---
from app.services.loaders import clear_vectorstore_cache
from .loaders import get_embedder, get_vectorstore

# --- Configuration & Constants ---
embedding_model = get_embedder()

TARGET_TOPIC = "Philippine cultural history, indigenous traditions, national heritage, local society, and historical events of the Philippines."
DOC_THRESHOLD = 0.45


# ==========================================
# --- Helper Functions (Pure Logic) ---
# ==========================================

def sha1_of_file(path: str, buf_size: int = 1024 * 1024) -> str:
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

def _extract_text_from_pdf(pdf_path: str) -> list[tuple[int, str]]:
    """Extracts selectable text from a PDF, returning a list of (page_num, text)."""
    page_texts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text(x_tolerance=1, y_tolerance=2) or ""
            if text.strip():
                page_texts.append((page_num, text))
    return page_texts

def _chunk_text(page_texts: list[tuple[int, str]]) -> list[tuple[int, int, str]]:
    """Splits text semantically, then refines with a token splitter."""
    chunker = SemanticChunker(
        embeddings=embedding_model,
        breakpoint_threshold_type="percentile",
        breakpoint_threshold_amount=95,
        min_chunk_size=200,
    )
    token_splitter = TokenTextSplitter(
        chunk_size=240,
        chunk_overlap=50,
        encoding_name="cl100k_base"
    )

    chunks_with_pages = []
    for page_num, page_text in page_texts:
        try:
            semantic_chunks = chunker.split_text(page_text)
        except Exception as e:
            print(f"Semantic chunking warning on page {page_num}: {e}")
            semantic_chunks = [page_text]

        for sem_chunk in semantic_chunks:
            final_sub_chunks = token_splitter.split_text(sem_chunk)
            for sub in final_sub_chunks:
                chunks_with_pages.append((page_num, len(chunks_with_pages) + 1, sub))
                
    return chunks_with_pages

def _evaluate_relevance(raw_texts: list[str]) -> tuple[float, list]:
    """Scores the document against the target topic and returns (score, chunk_vectors)."""
    target_vector = embedding_model.embed_query(TARGET_TOPIC)
    chunk_vectors = embedding_model.embed_documents(raw_texts)
    
    def get_cosine_similarity(v1, v2):
        return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

    similarities = [get_cosine_similarity(vec, target_vector) for vec in chunk_vectors]
    similarities.sort(reverse=True)
    
    top_20_percent_count = max(1, int(len(similarities) * 0.2))
    document_score = sum(similarities[:top_20_percent_count]) / top_20_percent_count
    
    return document_score, chunk_vectors


# ==========================================
# --- Main Processors ---
# ==========================================

def process_file(file_path: str, filename: str):
    """
    Processes a file (PDF or DOCX) into chunks and stores them in FAISS.
    Returns: (num_chunks, output_path)
    """
    extension = Path(file_path).suffix.lower()
    processing_path = file_path
    temp_pdf_path = None

    try:
        # 1. Handle DOCX Conversion
        if extension == '.docx':
            print(f"DOCX file detected. Converting '{filename}' to temporary PDF...")
            temp_pdf_path = os.path.join(tempfile.gettempdir(), f"{Path(filename).stem}.pdf")
            docx2pdf.convert(file_path, temp_pdf_path)
            processing_path = temp_pdf_path
            print("Conversion complete.")
        elif extension != '.pdf':
            print(f"Unsupported file type: '{extension}'. Skipping.")
            return 0, None

        # 2. Extract Text
        page_texts = _extract_text_from_pdf(processing_path)
        if not page_texts:
            print(f"No text extracted from '{filename}'. Aborting.")
            return 0, None

        # 3. Chunk Text & Prepare Metadata
        chunks_with_pages = _chunk_text(page_texts)
        source_sha1 = sha1_of_file(file_path)
        created_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        
        raw_texts = [chunk for _, _, chunk in chunks_with_pages]
        raw_metadatas = [
            {"id": make_chunk_id(source_sha1, p_num, g_idx, p_idx), "source": filename, "page": p_num, "created_at": created_at}
            for g_idx, (p_num, p_idx, _) in enumerate(chunks_with_pages)
        ]

        # 4. Evaluate Semantic Relevance
        print(f"Evaluating document '{filename}' for relevance...")
        document_score, chunk_vectors = _evaluate_relevance(raw_texts)
        print(f"Document relevance score: {document_score:.3f} (Threshold: {DOC_THRESHOLD})")

        if document_score < DOC_THRESHOLD:
            print(f"Document '{filename}' REJECTED. Did not meet the semantic threshold.")
            try:
                if Path(file_path).exists():
                    Path(file_path).unlink()
                    print(f"Deleted rejected file from storage: {file_path}")
            except Exception as e:
                print(f"Warning: Could not delete rejected file '{file_path}': {e}")
            return 0, None
            
        print(f"Document '{filename}' PASSED. Adding {len(raw_texts)} chunks to database.")

        # 5. Save to Storage (FAISS & JSONL)
        base_dir = Path("data_store")
        index_dir = base_dir / "vector_database"
        output_dir = base_dir / "chunked_output"
        output_dir.mkdir(parents=True, exist_ok=True)
        index_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{Path(filename).stem}_chunks.jsonl"

        index_file = index_dir / "index.faiss"
        if index_file.exists():
            vectorstore = get_vectorstore(allow_unsafe=True)
            vectorstore.add_embeddings(text_embeddings=list(zip(raw_texts, chunk_vectors)), metadatas=raw_metadatas)
        else:
            vectorstore = FAISS.from_embeddings(
                text_embeddings=list(zip(raw_texts, chunk_vectors)), 
                embedding=embedding_model, 
                metadatas=raw_metadatas, 
                distance_strategy=DistanceStrategy.COSINE
            )
        vectorstore.save_local(str(index_dir))

        with open(output_path, "w", encoding="utf-8") as f:
            for i, chunk_text in enumerate(raw_texts):
                f.write(json.dumps({"content": chunk_text, "metadata": raw_metadatas[i]}, ensure_ascii=False) + "\n")

        return len(raw_texts), output_path
    
    finally:
        # 6. Clean up temp PDF
        if temp_pdf_path and os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)


def delete_file_data(filename: str, upload_dir: Path) -> dict:
    """
    Completely removes a file's existence from the system (Files + Vector DB).
    """
    base_dir = Path("data_store")
    index_dir = base_dir / "vector_database"
    output_dir = base_dir / "chunked_output"
    
    file_path = upload_dir / filename
    jsonl_path = output_dir / f"{Path(filename).stem}_chunks.jsonl"
    
    report = {"file_deleted": False, "jsonl_deleted": False, "vectors_deleted": 0}

    # 1. Delete Physical Files
    if file_path.exists():
        file_path.unlink()
        report["file_deleted"] = True
    
    if jsonl_path.exists():
        jsonl_path.unlink()
        report["jsonl_deleted"] = True

    # 2. Clean FAISS Vector Store
    try:
        if index_dir.exists():
            vectorstore = get_vectorstore(allow_unsafe=True)
            ids_to_delete = [
                doc_id for doc_id, doc in vectorstore.docstore._dict.items() 
                if doc.metadata.get("source") == filename
            ]
            
            if ids_to_delete:
                vectorstore.delete(ids_to_delete)
                vectorstore.save_local(str(index_dir))
                clear_vectorstore_cache()
                report["vectors_deleted"] = len(ids_to_delete)
                print(f"Removed {len(ids_to_delete)} vectors for '{filename}' from FAISS.")
            else:
                print(f"No vectors found in FAISS for '{filename}'.")
                
    except Exception as e:
        print(f"Error cleaning FAISS: {e}")
    
    return report