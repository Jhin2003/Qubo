from pathlib import Path

from langchain.vectorstores import FAISS
from langchain.embeddings import HuggingFaceEmbeddings




  
embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

# Load the FAISS index
def load_faiss_index(index_dir: str):
    vectorstore = FAISS.load_local(index_dir, embedding_model, allow_dangerous_deserialization=True)
    return vectorstore

# Search the FAISS index
def search_vectorstore(query: str, index_dir: str, k: int = 3):
     
    
    vectorstore = load_faiss_index(index_dir)

   
    results = vectorstore.similarity_search_with_relevance_scores(query, k=5)

    print(f"\n \n \n Search results: {results}")
    context = " ".join([result[0].page_content for result in results])

    print(context)
   
    return context


    