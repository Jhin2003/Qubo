from langchain.chains import RetrievalQA
from langchain.chains.question_answering import load_qa_chain
from langchain.prompts import PromptTemplate
from langchain.llms import Ollama



# LLM setup (using Ollama in this case)
async def generate_response(context: str, query: str):
    # Initialize the LLM (you can use any LLM here)
    llm = Ollama(model="mistral:instruct")

    
    prompt = f"""
    You are a helpful assistant. 
    Use the provided context to answer the question as accurately as possible. 

    - If the context contains relevant information, base your answer strictly on it. 
    - If the context does not contain the answer, respond using your own knowledge. 
    - Be clear and concise.

    Context:
    {context}

    Question:
    {query}

    Answer:
    """


    # Generate the response using the LLM
    response = llm(prompt)


    return response