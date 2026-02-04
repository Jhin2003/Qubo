from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import List, Optional
# You'll likely need a new service function for the rephrasing step
from app.services.llm_service import generate_response, contextualize_query
from app.services.retrieval_service import search_vectorstore

router = APIRouter()

messages_store = [] # Warning: Global variables are not thread-safe in production!

class Message(BaseModel):
    sender: str
    text: str
    source: Optional[str] = None
    mode: str = "fast"

@router.post("/chat")
async def chat(request: Request, messages: List[Message]):

    if await request.is_disconnected():
        print("Client disconnected. Aborting request.")
        return {"response": "Request canceled", "sources": []}
    # 1. EXTRACT CURRENT MESSAGE
    # We assume the last message is the new user input
    current_msg = messages[-1]
    user_message = current_msg.text
    
    # 2. SLIDING WINDOW (Prevent Context Flooding)
    # Grab only the last 6 messages (excluding the current one) for history
    # This keeps context relevant but manageable.
    history_window = messages[:-1][-6:] 
    
    # Format history as string or list of dicts for the LLM
    # Example format: "User: hello\nBot: hi there..."
    formatted_history = [
        {"role": m.sender, "content": m.text} for m in history_window
    ]

    # 3. CONTEXTUALIZE (The "Condense" Step)
    # If there is history, we must rewrite the query to handle pronouns.
    # e.g. History: "Who is Rizal?" -> User: "Where did he die?"
    # standalone_query becomes: "Where did Jose Rizal die?"

    if history_window:
        standalone_query = await contextualize_query(formatted_history, user_message)
        print(f"Original: {user_message} -> Rewritten: {standalone_query}")
    else:
        standalone_query = user_message
    
    
    if await request.is_disconnected():
        print("Client disconnected before retrieval. Stopping.")
        return {"response": "Request canceled", "sources": []}
      

  
    # 4. RETRIEVE using the STANDALONE query (not the raw user message)
    has_source = bool(current_msg.source)
    if has_source:
        context, sources = await search_vectorstore(
            standalone_query,  # <--- CHANGED
            index_dir="data_store/vector_database",
            source=current_msg.source,
            mode=current_msg.mode,

        )
    else:
        context, sources = await search_vectorstore(
            standalone_query,  # <--- CHANGED
            index_dir="data_store/vector_database",
            mode= current_msg.mode
        )

    if await request.is_disconnected():
        print("Client disconnected before generation. Stopping.")
        return {"response": "Request canceled", "sources": []}
    # 5. GENERATE
    # Pass the history window + context + current message
    llm_response = await generate_response(
        context=context, 
        query=user_message, 
        history=formatted_history, # <--- Pass the windowed history here
        mode=current_msg.mode
    )

    # ... (Rest of your storage logic) ...
    bot_response = f"{llm_response}"
    messages_store.append({"sender": "user", "text": user_message})
    messages_store.append({"sender": "bot", "text": bot_response})

    return {"response": bot_response, "sources": sources}