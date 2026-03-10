from functools import lru_cache

import torch

from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from sentence_transformers import CrossEncoder
from langchain_community.vectorstores.utils import DistanceStrategy

from together import Together
import os

from transformers import pipeline

# 1. Define the model name

EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
CE_MODEL_NAME = "BAAI/bge-reranker-base"
CC_MODEL_NAME = "grahamaco/question-complexity-classifier"
INDEX_DIR = "data_store/vector_database"

from langchain_core.embeddings import Embeddings


class TogetherEmbeddings(Embeddings):
    def __init__(self, model="intfloat/multilingual-e5-large-instruct"):
        self.client = Together(api_key="f093074f102974466d625db36d8bd171b92df916fa78eb7b91faa9108e6ed5c2")
        self.model = model

    def embed_documents(self, texts):
        response = self.client.embeddings.create(
            model=self.model,
            input=texts
        )
        return [item.embedding for item in response.data]

    def embed_query(self, text):
        response = self.client.embeddings.create(
            model=self.model,
            input=[text]
        )
        return response.data[0].embedding

@lru_cache(maxsize=1)
def get_embedder():
    return TogetherEmbeddings()


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
        allow_dangerous_deserialization=bool(allow_unsafe),
        distance_strategy=DistanceStrategy.COSINE
    )



def warmup():
    # Embeddings: force a real encode to finish loading/compiling
    emb = get_embedder()
    try:
        emb.embed_documents(["__warmup__"])
    except Exception as e:
        print(f"Skipping FAISS warmup: {e}")

        # Cross-encoder: force a real predict
    ce = get_cross_encoder()
    ce.predict([("__warmup__", "__warmup__")])


    # FAISS: load if present
    try:
        _ = get_vectorstore(allow_unsafe=True)
    except Exception as e:
        print(f"Skipping FAISS warmup: {e}")


def clear_vectorstore_cache():
    """Forces the system to reload FAISS from disk next time it's asked."""
    print("[SYSTEM] Clearing VectorStore Memory Cache...")
    # This clears the specific cache for the get_vectorstore function
    get_vectorstore.cache_clear()

def invalidate_all():
    get_vectorstore.cache_clear()
    get_embedder.cache_clear()
    get_cross_encoder.cache_clear()
    
