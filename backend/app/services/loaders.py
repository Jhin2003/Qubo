from functools import lru_cache

from langchain.vectorstores import FAISS
from langchain.embeddings import HuggingFaceEmbeddings
from sentence_transformers import CrossEncoder

EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
CE_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
index_dir = "data_store/vector_database"

@lru_cache(maxsize=1)
def get_embedder():
    return HuggingFaceEmbeddings(model_name=EMBED_MODEL_NAME)

@lru_cache(maxsize=1)
def get_cross_encoder():
    return CrossEncoder(CE_MODEL_NAME)

@lru_cache(maxsize=4)
def get_vectorstore(allow_unsafe: bool = False):
    emb = get_embedder()
    return FAISS.load_local(
        index_dir,
        emb,
        allow_dangerous_deserialization=bool(allow_unsafe)
    )


def warmup():
    # Embeddings: force a real encode to finish loading/compiling
    emb = get_embedder()
    try:
        emb.embed_documents(["__warmup__"])
        print("Done warmup of embedder.")
    except Exception:
        # fallback for older LangChain versions
        emb.client.encode(["__warmup__"], convert_to_numpy=True, normalize_embeddings=False)

    # Cross-encoder: force a real predict
    ce = get_cross_encoder()
    ce.predict([("__warmup__", "__warmup__")])

    # FAISS: load if present
    try:
        _ = get_vectorstore(allow_unsafe=True)
    except Exception as e:
        print(f"Skipping FAISS warmup: {e}")


def invalidate_all():
    get_vectorstore.cache_clear()
    get_embedder.cache_clear()
    get_cross_encoder.cache_clear()
