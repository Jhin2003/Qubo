from langchain.chains import RetrievalQA
from langchain.chains.question_answering import load_qa_chain
from langchain.prompts import PromptTemplate
from langchain.llms import Ollama



# LLM setup (using Ollama in this case)
async def generate_response(context: str, query: str):
    # Initialize the LLM (you can use any LLM here)
    llm = Ollama(model="mistral:instruct")

    
    prompt = f"""
    
    if context is empty or irelevant say "I cannot answer that because I do not have information about it".

    Context:
    {context}

    Question:
    {query}

    Answer:
    """


    # Generate the response using the LLM
    response = llm(prompt)


    return response


# LLM setup (using Ollama in this case)
async def generate_question(context: str, query: str):
    # Initialize the LLM (you can use any LLM here)
    llm = Ollama(model="mistral:instruct")

    
    prompt = f"""
 
    your task is to remove irrelevant context based on the question.

    Context:
    {context}

    Question:
    {query}

    Summarized Context:
    """


    # Generate the response using the LLM
    response = llm(prompt)


    return response