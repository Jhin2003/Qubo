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
