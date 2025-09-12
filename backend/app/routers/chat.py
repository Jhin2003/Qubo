from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
from app.services.retrieval_service import search_vectorstore
from app.services.llm_service import generate_response, generate_question

router = APIRouter()

# A list to store the messages
messages_store = []

class Message(BaseModel):
    sender: str
    text: str

@router.post("/chat")
async def chat(messages: List[Message]):
    user_message = messages[-1].text  # Get the last user message

    # Retrieve relevant chunks and sources
    context, sources = search_vectorstore(
        user_message,
        index_dir="data_store/vector_database",
    )

    # Pass only the context to the LLM
    llm_response = await generate_question(context, user_message)
 

    # Build bot response (LLM answer + optional sources text if you want)
    bot_response = f"{llm_response}"

    # Store the messages in memory
    messages_store.append({"sender": "user", "text": user_message})
    messages_store.append({"sender": "bot", "text": bot_response})

    # Return both bot response and sources (for frontend display)
    return {"response": bot_response, "sources": sources}


@router.get("/chat")
async def get_chat():
    return {"messages": messages_store}
