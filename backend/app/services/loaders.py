from functools import lru_cache
import torch
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_community.vectorstores.utils import DistanceStrategy

from sentence_transformers import SentenceTransformer, CrossEncoder
from langchain_core.embeddings import Embeddings


# ----------------------------
# BASE PATHS
# ----------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent
INDEX_DIR = BASE_DIR / "data_store" / "vector_database"


EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
CE_MODEL_NAME = "BAAI/bge-reranker-base"


# ----------------------------
# EMBEDDINGS WRAPPER (FAISS COMPATIBLE)
# ----------------------------
class STEmbeddings(Embeddings):
    def __init__(self, model_name: str):
        self.model = SentenceTransformer(model_name)

    def embed_documents(self, texts):
        return self.model.encode(texts, convert_to_numpy=True).tolist()

    def embed_query(self, text):
        return self.model.encode(text, convert_to_numpy=True).tolist()


# ----------------------------
# EMBEDDINGS (cached, download once)
# ----------------------------
@lru_cache(maxsize=1)
def get_embedder():
    return STEmbeddings(EMBED_MODEL_NAME)


# ----------------------------
# CROSS ENCODER (cached, download once)
# ----------------------------
@lru_cache(maxsize=1)
def get_cross_encoder():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    return CrossEncoder(CE_MODEL_NAME, device=device)


# ----------------------------
# VECTORSTORE (FAISS)
# ----------------------------
@lru_cache(maxsize=1)
def get_vectorstore(allow_unsafe: bool = False):
    emb = get_embedder()

    return FAISS.load_local(
        str(INDEX_DIR),
        emb,
        allow_dangerous_deserialization=bool(allow_unsafe),
        distance_strategy=DistanceStrategy.COSINE
    )


# ----------------------------
# WARMUP (safe, no broken calls)
# ----------------------------
def warmup():
    print("[WARMUP] Loading models...")

    try:
        emb = get_embedder()
        emb.embed_documents(["warmup"])
    except Exception as e:
        print(f"[WARN] Embedding warmup failed: {e}")

    try:
        ce = get_cross_encoder()
        ce.predict([("warmup", "warmup")])
    except Exception as e:
        print(f"[WARN] CrossEncoder warmup failed: {e}")

    try:
        _ = get_vectorstore(allow_unsafe=True)
    except Exception as e:
        print(f"[WARN] FAISS warmup skipped: {e}")


# ----------------------------
# CACHE CONTROL
# ----------------------------
def clear_vectorstore_cache():
    print("[SYSTEM] Clearing VectorStore Cache")
    get_vectorstore.cache_clear()


def invalidate_all():
    get_vectorstore.cache_clear()
    get_embedder.cache_clear()
    get_cross_encoder.cache_clear()