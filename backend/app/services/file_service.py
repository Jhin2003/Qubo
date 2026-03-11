import os
import json
import hashlib
import io
import tempfile
from datetime import datetime
from pathlib import Path

# --- Dependencies ---
import pdfplumber
from langchain_text_splitters import TokenTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_experimental.text_splitter import SemanticChunker
from app.services.loaders import clear_vectorstore_cache
from langchain_community.vectorstores.utils import DistanceStrategy
import numpy as np

# --- Local Imports ---
from .loaders import get_embedder, get_vectorstore

# --- Configuration ---
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

# --- Main Processor ---
def process_file(file_path: str, filename: str):
    """
    Processes a PDF file into chunks and stores them in FAISS.
    Includes a semantic threshold check for 'Philippine cultural history'.
    Returns: (num_chunks, output_path)
    """
    extension = Path(file_path).suffix.lower()
    
    # Check for PDF extension only
    if extension != '.pdf':
        print(f"Unsupported file type: '{extension}'. Only PDF is supported. Skipping.")
        if os.path.exists(file_path): os.remove(file_path) # Clean up invalid uploads immediately
        return 0, None

    # --- 1. Extract text from the PDF ---
    page_texts = []
    
    try:
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                text = page.extract_text(x_tolerance=1, y_tolerance=2) or ""
                if text.strip():
                    page_texts.append((page_num, text))
        
        if not page_texts:
            print(f"No text extracted from '{filename}'. Aborting.")
            if os.path.exists(file_path): os.remove(file_path)
            return 0, None

        # --- 2. Semantic Thresholding (Gatekeeper) ---
        print(f"Evaluating relevance of '{filename}'...")
        
        # Define what we are looking for
        target_topic = "Philippine cultural history, history of the Philippines, Filipino heritage, indigenous traditions, Filipino icons, and historical events."
        target_vector = embedding_model.embed_query(target_topic)
        
        # Sample the first few pages to gauge the document's topic (max ~3000 chars to avoid token limits)
        sample_text = " ".join([t for _, t in page_texts[:5]])[:3000]
        doc_vector = embedding_model.embed_query(sample_text)
        
        # Calculate Cosine Similarity
        dot_product = np.dot(target_vector, doc_vector)
        norm_a = np.linalg.norm(target_vector)
        norm_b = np.linalg.norm(doc_vector)
        similarity = dot_product / (norm_a * norm_b)
        
        # Adjust this threshold based on your specific embedding model (0.5 to 0.7 is usually a good starting point)
        RELEVANCE_THRESHOLD = 0.5
        
        if similarity < RELEVANCE_THRESHOLD:
            print(f"❌ Rejected '{filename}': Not relevant to Philippine cultural history. (Score: {similarity:.2f})")
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"🗑️ Deleted invalid file: {file_path}")
            return 0, None
            
        print(f"✅ Document passed relevance check (Score: {similarity:.2f}). Proceeding with chunking...")

        # --- 3. Setup Directories ---
        base_dir = Path("data_store")
        output_dir = base_dir / "chunked_output"
        index_dir = base_dir / "vector_database"
        
        output_dir.mkdir(parents=True, exist_ok=True)
        index_dir.mkdir(parents=True, exist_ok=True)
        
        output_path = output_dir / f"{Path(filename).stem}_chunks.jsonl"

        # --- 4. Chunking Configuration ---
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
        
        # --- 5. Processing Loop ---
        for page_num, page_text in page_texts:
            try:
                semantic_chunks = chunker.split_text(page_text)
            except Exception as e:
                print(f"Semantic chunking warning on page {page_num}: {e}")
                semantic_chunks = [page_text]

            for sem_chunk in semantic_chunks:
                final_sub_chunks = token_splitter.split_text(sem_chunk)
                for sub in final_sub_chunks:
                    chunks_with_pages.append((page_num, len(chunks_with_pages)+1, sub))

        # --- 6. Metadata Preparation ---
        source_sha1 = sha1_of_file(file_path)
        created_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        
        texts = [chunk for _, _, chunk in chunks_with_pages]
        metadatas = [
            {
                "id": make_chunk_id(source_sha1, p_num, g_idx, p_idx), 
                "source": filename, 
                "page": p_num, 
                "created_at": created_at
            }
            for g_idx, (p_num, p_idx, _) in enumerate(chunks_with_pages)
        ]

        # --- 7. FAISS Operations ---
        index_file = index_dir / "index.faiss"
        store_file = index_dir / "index.pkl"
        
        if index_file.exists() and store_file.exists():
            print(f"Updating existing FAISS index at '{index_dir}'")
            vectorstore = get_vectorstore(allow_unsafe=True)
            vectorstore.add_texts(texts=texts, metadatas=metadatas)
        else:
            print(f"Creating a new FAISS index at '{index_dir}'")
            vectorstore = FAISS.from_texts(
                texts=texts, 
                embedding=embedding_model, 
                metadatas=metadatas, 
                distance_strategy=DistanceStrategy.COSINE
            )
        
        vectorstore.save_local(str(index_dir))

        # --- 8. Save JSONL Output ---
        with open(output_path, "w", encoding="utf-8") as f:
            for i, chunk_text in enumerate(texts):
                line = json.dumps({"content": chunk_text, "metadata": metadatas[i]}, ensure_ascii=False)
                f.write(line + "\n")

        print(f"Processed {len(texts)} chunks for '{filename}'.")
        return len(chunks_with_pages), output_path

    except Exception as e:
        print(f"An error occurred while processing '{filename}': {e}")
        # Clean up the file if it failed midway
        if os.path.exists(file_path):
            os.remove(file_path)
        return 0, None


def delete_file_data(filename: str, upload_dir: Path) -> dict:
    """
    Completely removes a file's existence from the system:
    1. Deletes the physical PDF/DOCX from 'data_store/pdfs/'
    2. Deletes the JSONL chunks file from 'data_store/chunked_output/'
    3. Scans FAISS, finds all vectors with metadata source==filename, and removes them.
    4. Saves the cleaned FAISS index back to disk.
    """
    base_dir = Path("data_store")
    index_dir = base_dir / "vector_database"
    output_dir = base_dir / "chunked_output"
    
    # 1. Define paths
    file_path = upload_dir / filename
    jsonl_path = output_dir / f"{Path(filename).stem}_chunks.jsonl"
    
    report = {
        "file_deleted": False,
        "jsonl_deleted": False,
        "vectors_deleted": 0
    }

    # 2. Delete Physical Files
    if file_path.exists():
        file_path.unlink()
        report["file_deleted"] = True
    
    if jsonl_path.exists():
        jsonl_path.unlink()
        report["jsonl_deleted"] = True

    # 3. Clean FAISS Vector Store
    # We must load the store to find which IDs belong to this file
    try:
        if index_dir.exists():
            vectorstore = get_vectorstore(allow_unsafe=True)
            
            # FAISS (LangChain wrapper) stores documents in a docstore dict.
            # We iterate to find IDs where metadata['source'] matches our filename.
            ids_to_delete = []
            for doc_id, doc in vectorstore.docstore._dict.items():
                if doc.metadata.get("source") == filename:
                    ids_to_delete.append(doc_id)
            
            if ids_to_delete:
                # Delete from memory
                isDeleted = vectorstore.delete(ids_to_delete)
                print(isDeleted)
                # Save changes to disk
                vectorstore.save_local(str(index_dir))
                report["vectors_deleted"] = len(ids_to_delete)
                print(f"Removed {len(ids_to_delete)} vectors for '{filename}' from FAISS.")
                clear_vectorstore_cache()
            else:
                print(f"No vectors found in FAISS for '{filename}'.")
         
                
    except Exception as e:
        print(f"Error cleaning FAISS: {e}")
        # We don't raise here because we still want to report that files were deleted
    
    return report