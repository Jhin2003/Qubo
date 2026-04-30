from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import List, Optional
from app.services.llm_service import generate_response, contextualize_query
from app.services.retrieval_service import search_vectorstore
import asyncio
router = APIRouter()

messages_store = [] 

class Message(BaseModel):
    sender: str
    text: str
    source: Optional[str] = None
    mode: str = "fast"

@router.post("/chat")
async def chat(request: Request, messages: List[Message]):
  
    current_msg = messages[-1]
    user_message = current_msg.text
    history_window = messages[:-1][-6:] 
    
    formatted_history = [
        {"role": m.sender, "content": m.text} for m in history_window
    ]


    if history_window:
  
        standalone_query = await contextualize_query(
         
            formatted_history, 
            user_message
        )
        print(f"Original: {user_message} -> Rewritten: {standalone_query}")
    else:
        standalone_query = user_message
    

    has_source = bool(current_msg.source)
    

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



    llm_response = await generate_response(
        context=context, 
        query=user_message, 
        history=formatted_history, 
        mode=current_msg.mode
    )        

  
    bot_response = f"{llm_response}"
    messages_store.append({"sender": "user", "text": user_message})
    messages_store.append({"sender": "bot", "text": bot_response})

    return {"response": bot_response, "sources": sources}