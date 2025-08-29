from langchain.chains import RetrievalQA
from langchain.chains.question_answering import load_qa_chain
from langchain.prompts import PromptTemplate
from langchain.llms import Ollama



# LLM setup (using Ollama in this case)
async def generate_response(context: str, query: str):
    # Initialize the LLM (you can use any LLM here)
    llm = Ollama(model="mistral:instruct")

    
    prompt = f"Context: {context}\n\nQuestion: {query}\n\nAnswer:"

    # Generate the response using the LLM
    response = llm(prompt)


    return response