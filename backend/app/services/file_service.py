import os
import json
import hashlib
import tempfile
from datetime import datetime
from pathlib import Path
import numpy as np

from supabase import create_client, Client

# --- Dependencies ---
import pdfplumber
import docx2pdf 
from langchain_text_splitters import TokenTextSplitter
from langchain_experimental.text_splitter import SemanticChunker
from dotenv import load_dotenv

# 🔥 NEW IMPORT: LangChain's Supabase Vector Store
from langchain_community.vectorstores import SupabaseVectorStore

# --- Local Imports ---
# NOTE: You probably don't need clear_vectorstore_cache or get_vectorstore 
# from loaders.py anymore if they are FAISS-specific, but I've left get_embedder.
from .loaders import get_embedder 

# --- Configuration & Constants ---
load_dotenv()
embedding_model = get_embedder()

TARGET_TOPIC = "Philippine cultural history, indigenous traditions, national heritage, local society, and historical events of the Philippines."
DOC_THRESHOLD = 0.45

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Helper Functions ---

def sha1_of_file(path: str, buf_size: int = 1024 * 1024) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(buf_size), b""):
            h.update(chunk)
    return h.hexdigest()

def make_chunk_id(source_sha1: str, page: int, global_idx: int, page_idx: int) -> str:
    core = f"{source_sha1[:12]}:p{page}:g{global_idx}:k{page_idx}"
    return hashlib.sha1(core.encode("utf-8")).hexdigest()

def _extract_text_from_pdf(pdf_path: str) -> list[tuple[int, str]]:
    page_texts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text(x_tolerance=1, y_tolerance=2) or ""
            if text.strip():
                page_texts.append((page_num, text))
    return page_texts

def _chunk_text(page_texts: list[tuple[int, str]]) -> list[tuple[int, int, str]]:
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
    target_vector = embedding_model.embed_query(TARGET_TOPIC)
    chunk_vectors = embedding_model.embed_documents(raw_texts)
    
    def get_cosine_similarity(v1, v2):
        return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

    similarities = [get_cosine_similarity(vec, target_vector) for vec in chunk_vectors]
    similarities.sort(reverse=True)
    
    top_20_percent_count = max(1, int(len(similarities) * 0.2))
    document_score = sum(similarities[:top_20_percent_count]) / top_20_percent_count
    
    return document_score, chunk_vectors

def upload_file_to_supabase(file_path: str, bucket: str = "uploads") -> str:
    file_name = Path(file_path).name

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    response = supabase.storage.from_(bucket).upload(
        path=file_name,
        file=file_bytes,
        file_options={
            "content-type": "application/pdf",
            "upsert": "true"
        }
    )

    return supabase.storage.from_(bucket).get_public_url(file_name)
# --- Main Processors ---

def process_file(file_path: str, filename: str, content_type: str) -> int:
    extension = Path(file_path).suffix.lower()
    processing_path = file_path
    temp_pdf_path = None

    try:
        if extension == '.docx':
            temp_pdf_path = os.path.join(tempfile.gettempdir(), f"{Path(filename).stem}.pdf")
            docx2pdf.convert(file_path, temp_pdf_path)
            processing_path = temp_pdf_path
            content_type = "application/pdf"
        elif extension != '.pdf':
            return 0

        # Extract Text
        page_texts = []
        with pdfplumber.open(processing_path) as pdf:
            for i, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if text: page_texts.append((i, text))

        if not page_texts: return 0

        # Semantic Chunking
        chunker = SemanticChunker(embedding_model, breakpoint_threshold_type="percentile")
        token_splitter = TokenTextSplitter(chunk_size=240, chunk_overlap=50)
        
        all_chunks = []
        for p_num, p_text in page_texts:
            s_chunks = chunker.split_text(p_text)
            for sc in s_chunks:
                for final_chunk in token_splitter.split_text(sc):
                    all_chunks.append((p_num, final_chunk))

        # Relevance Check
        texts_only = [c[1] for c in all_chunks]
        doc_score, vectors = _evaluate_relevance(texts_only)
        
        if doc_score < DOC_THRESHOLD:
            return 0

        # 1. Upload Raw File to Storage
        if not upload_file_to_supabase(file_path, content_type):
            return 0

        # 2. Upload Vectors to DB
        source_sha1 = sha1_of_file(file_path)
        rows = [{
            "content": all_chunks[i][1],
            "embedding": vectors[i],
            "metadata": {
                "source": filename,
                "page": all_chunks[i][0],
                "id": make_chunk_id(source_sha1, all_chunks[i][0], i)
            }
        } for i in range(len(all_chunks))]

        supabase.table("documents").insert(rows).execute()
        return len(all_chunks)
    
    finally:
        if temp_pdf_path and os.path.exists(temp_pdf_path): os.remove(temp_pdf_path)
        if os.path.exists(file_path): os.remove(file_path)

def delete_file_data(filename: str) -> dict:
    report = {"vectors_deleted": 0, "storage_deleted": False}
    try:
        # Delete from DB using arrow filter for JSONB metadata
        res = supabase.table("documents").delete().filter("metadata->>source", "eq", filename).execute()
        report["vectors_deleted"] = len(res.data) if res.data else 0
        
        # Delete from Storage
        supabase.storage.from_("uploads").remove([filename])
        report["storage_deleted"] = True
    except Exception as e:
        print(f"Delete error: {e}")
    return report