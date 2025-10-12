from langchain.chains import RetrievalQA
from langchain.chains.question_answering import load_qa_chain
from langchain.prompts import PromptTemplate
from langchain.llms import Ollama

import os

# Set CUDA_VISIBLE_DEVICES to use only GPUs 0 and 1
os.environ["CUDA_VISIBLE_DEVICES"] = "0,1"

llm = Ollama(model="mistral:instruct")

async def generate_response(context: str, query: str):
    

    prompt = f"""
SYSTEM: You are an academic assistant. Use ONLY the information found in the provided context chunks. 
Do NOT invent facts or citations. If the answer cannot be produced from the context, reply exactly: "I don't know based on the given context."

CITATION RULES:
- For each factual statement, add an inline citation in this format: [source, page], e.g., [intro, 8].
- Only cite sources present in the context. Do not invent authors, years, or page numbers.

FEW-SHOT EXAMPLES:
Context:
[1] Source: Intro, Page: 8
Content: A sorting algorithm is a method used to rearrange a list of elements into a particular order. Common examples include quicksort, mergesort, and bubble sort.

Question: What is a sorting algorithm?
Desired Output:
A sorting algorithm is a method to rearrange a list of elements into a particular order. Common examples include quicksort, mergesort, and bubble sort [intro, 8].

-----
NOW THE QUERY AND CONTEXT:
Question:
{query}

Context:
{context}

Return the answer in a concise, readable format with inline citations like [source, page]. Do NOT return JSON or extra commentary.
"""
    
    return llm(prompt)




    

