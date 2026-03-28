from functools import lru_cache

import torch

from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from sentence_transformers import CrossEncoder
from langchain_community.vectorstores.utils import DistanceStrategy

from pathlib import Path
from transformers import pipeline

# Base directory (project root)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# 1. Define the model name
EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
CE_MODEL_NAME = "BAAI/bge-reranker-base"
CC_MODEL_NAME = "grahamaco/question-complexity-classifier"

# ✅ FIXED PATH (absolute, portable)
INDEX_DIR = BASE_DIR / "data_store" / "vector_database"


@lru_cache(maxsize=1)
def get_embedder():
    return HuggingFaceEmbeddings(model_name=EMBED_MODEL_NAME)


@lru_cache(maxsize=1)
def get_cross_encoder():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    return CrossEncoder(CE_MODEL_NAME, max_length=512, device=device)


@lru_cache(maxsize=1)
def get_vectorstore(allow_unsafe: bool = False):
    emb = get_embedder()
    return FAISS.load_local(
        str(INDEX_DIR),  # ✅ ensure string path
        emb,
        allow_dangerous_deserialization=bool(allow_unsafe),
        distance_strategy=DistanceStrategy.COSINE
    )


@lru_cache(maxsize=1)
def get_complexity_classifier():
    device_id = 0 if torch.cuda.is_available() else -1
    
    return pipeline(
        "text-classification",
        model=CC_MODEL_NAME,
        device=device_id
    )


def warmup():
    emb = get_embedder()
    try:
        emb.embed_documents(["__warmup__"])
    except Exception:
        emb.client.encode(
            ["__warmup__"],
            convert_to_numpy=True,
            normalize_embeddings=False
        )

    ce = get_cross_encoder()
    ce.predict([("__warmup__", "__warmup__")])

    try:
        classifier = get_complexity_classifier()
        classifier("__warmup__")
        print("Complexity Classifier warmed up successfully.")
    except Exception as e:
        print(f"Skipping Complexity Classifier warmup: {e}")

    try:
        _ = get_vectorstore(allow_unsafe=True)
    except Exception as e:
        print(f"Skipping FAISS warmup: {e}")


def clear_vectorstore_cache():
    print("[SYSTEM] Clearing VectorStore Memory Cache...")
    get_vectorstore.cache_clear()


def invalidate_all():
    get_vectorstore.cache_clear()
    get_embedder.cache_clear()
    get_cross_encoder.cache_clear()
    get_complexity_classifier.cache_clear()