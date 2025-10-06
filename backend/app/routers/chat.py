from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional
from app.services.retrieval_service import search_vectorstore
from app.services.llm_service import generate_response, generate_question

router = APIRouter()

# A list to store the messages
messages_store = []

class Message(BaseModel):
    sender: str
    text: str
    source: Optional[str] = None  # <-- optional

@router.post("/chat")
async def chat(messages: List[Message]):

    last_user = next((m for m in reversed(messages) if m.sender == "user"), messages[-1])

    # did this request include a source?
    has_source = bool(last_user.source)
    user_message = last_user.text
    print(has_source)
    # Retrieve relevant chunks and sources

    if has_source:
        context, sources = await search_vectorstore(
            user_message,
            index_dir="data_store/vector_database",
            source = last_user.source
        )
    else:
        context, sources = await search_vectorstore(
            user_message,
            index_dir="data_store/vector_database",
        )

    # Pass only the context to the LLM
    llm_response = await generate_response(context, user_message)

    print(llm_response)
 

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
