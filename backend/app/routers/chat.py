from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import List, Optional
# You'll likely need a new service function for the rephrasing step
from app.services.llm_service import generate_response, contextualize_query
from app.services.retrieval_service import search_vectorstore
import asyncio
router = APIRouter()

messages_store = [] # Warning: Global variables are not thread-safe in production!

class Message(BaseModel):
    sender: str
    text: str
    source: Optional[str] = None
    mode: str = "fast"

@router.post("/chat")
async def chat(request: Request, messages: List[Message]):
    # ... (Disconnect checks remain the same) ...

    # 1. EXTRACT CURRENT MESSAGE
    current_msg = messages[-1]
    user_message = current_msg.text
    history_window = messages[:-1][-6:] 
    
    formatted_history = [
        {"role": m.sender, "content": m.text} for m in history_window
    ]

    # --- FIX 1: Non-Blocking Contextualize ---
    if history_window:
        # We run the synchronous 'contextualize_query' in a separate thread
        standalone_query = await contextualize_query(
         
            formatted_history, 
            user_message
        )
        print(f"Original: {user_message} -> Rewritten: {standalone_query}")
    else:
        standalone_query = user_message
    
    # ... (Disconnect check) ...

    # --- FIX 2: Non-Blocking Retrieval ---
    # Assuming 'search_vectorstore' does heavy CPU work or file I/O
    has_source = bool(current_msg.source)
    
    # Define a helper lambda or partial to pass arguments cleanly to to_thread
    if has_source:
        context, sources = await search_vectorstore(
            standalone_query, 
            "data_store/vector_database", 
            mode=current_msg.mode,
            source=current_msg.source
        )
    else:
        context, sources = await search_vectorstore(
           
            standalone_query, 
            "data_store/vector_database", 
            mode=current_msg.mode
        )

    # ... (Disconnect check) ...

    # --- FIX 3: Non-Blocking Generation ---
    # This is the most critical one (LLM calls take the longest)
    llm_response = await generate_response(
        context=context, 
        query=user_message, 
        history=formatted_history, 
        mode=current_msg.mode
    )        

    # ... (Rest of logic) ...
    bot_response = f"{llm_response}"
    messages_store.append({"sender": "user", "text": user_message})
    messages_store.append({"sender": "bot", "text": bot_response})

    return {"response": bot_response, "sources": sources}