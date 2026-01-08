from functools import lru_cache

import torch

from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from sentence_transformers import CrossEncoder

from transformers import pipeline

# 1. Define the model name


EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
CE_MODEL_NAME = "BAAI/bge-reranker-base"
CC_MODEL_NAME = "grahamaco/question-complexity-classifier"

INDEX_DIR = "data_store/vector_database"


@lru_cache(maxsize=1)
def get_embedder():
    return HuggingFaceEmbeddings(model_name=EMBED_MODEL_NAME)


@lru_cache(maxsize=1)
def get_cross_encoder():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    # Let CrossEncoder load the model itself
    return CrossEncoder(CE_MODEL_NAME, max_length=512, device=device)

@lru_cache(maxsize=1)
def get_vectorstore(allow_unsafe: bool = False):
    emb = get_embedder()
    return FAISS.load_local(
        INDEX_DIR,
        emb,
        allow_dangerous_deserialization=bool(allow_unsafe)
    )

@lru_cache(maxsize=1)
def get_complexity_classifier():
    """
    Initializes and caches the query complexity classification pipeline.
    """
    # Check for GPU availability and assign to device 0 if available, otherwise use CPU (-1)
    device_id = 0 if torch.cuda.is_available() else -1
    
    return pipeline(
        "text-classification",
        model=CC_MODEL_NAME,
        # Assign the device for faster inference
        device=device_id
    )


def warmup():
    # Embeddings: force a real encode to finish loading/compiling
    emb = get_embedder()
    try:
        emb.embed_documents(["__warmup__"])
    
    except Exception:
        # fallback for older LangChain versions
        emb.client.encode(["__warmup__"], convert_to_numpy=True, normalize_embeddings=False)

    # Cross-encoder: force a real predict
    ce = get_cross_encoder()
    ce.predict([("__warmup__", "__warmup__")])

    try:
        classifier = get_complexity_classifier()
        # Run a minimal prediction to load the model onto the device
        classifier("__warmup__") 
        print("Complexity Classifier warmed up successfully.")
    except Exception as e:
        print(f"Skipping Complexity Classifier warmup: {e}")


    # FAISS: load if present
    try:
        _ = get_vectorstore(allow_unsafe=True)
    except Exception as e:
        print(f"Skipping FAISS warmup: {e}")


def invalidate_all():
    get_vectorstore.cache_clear()
    get_embedder.cache_clear()
    get_cross_encoder.cache_clear()
    get_complexity_classifier.cache_clear()
