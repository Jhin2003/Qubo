from langchain.chains import RetrievalQA
from langchain.chains.question_answering import load_qa_chain
from langchain.prompts import PromptTemplate
from langchain.llms import Ollama

import os



llm = Ollama(model="mistral:instruct")

async def generate_response(context: str, query: str):
    

    prompt = f"""
SYSTEM: You are a strict context assistant. Use ONLY the information found in the provided context. 
Do NOT invent facts or citations. If the answer cannot be produced from the context, reply exactly: "I don't know."

CITATION RULES:
- For each factual statement, add an inline citation in this format: [source, page], e.g., [intro, 8].
- Only cite sources present in the context.

FEW-SHOT EXAMPLES:
Context:
[1] Source: Intro, Page: 8
Content: A sorting algorithm is a method used to rearrange a list of elements into a particular order.

Question: What is a sorting algorithm?
Desired Output:
A sorting algorithm is a method to rearrange a list of elements into a particular order [intro, 8].

-----
Context:
[1] Source: Intro, Page: 8
Content: A sorting algorithm is a method used to rearrange a list of elements into a particular order.

Question: What is the capital of France?
Desired Output:
I don't know based on the given context.

-----
NOW THE QUERY AND CONTEXT:
Question:
{query}

Context:
{context}

Return the answer in a readable format with inline citations like [source, page]. No extra commentary.
"""
    
    return llm(prompt)




    

