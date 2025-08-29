from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import shutil
import os

from app.services.file_service import process_pdf_chunks

app = FastAPI()

# Allow CORS for all origins (for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins (for development)
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

# A list to store the messages
messages_store = []

class Message(BaseModel):
    sender: str
    text: str



# Directory to store uploaded PDFs
UPLOAD_DIR = "data_store/pdfs"
OUTPUT_DIR = "chunked_output"

os.makedirs(UPLOAD_DIR, exist_ok=True)

# POST endpoint to send messages
@app.post("/chat")
async def chat(messages: List[Message]):
    user_message = messages[-1].text  # Get the last user message
    bot_response = "Simulated bot response for: " + user_message

    # Store the messages in the global list
    messages_store.append({"sender": "user", "text": user_message})
    messages_store.append({"sender": "bot", "text": bot_response})

    return {"response": bot_response}

# GET endpoint to retrieve the sent messages
@app.get("/chat")
async def get_chat():
    return {"messages": messages_store}




@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    # Define the file path where the PDF will be saved
    file_path = os.path.join(UPLOAD_DIR, file.filename)

    try:
        # Save the file to the designated path
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # Define the output file path for chunked data
        output_path = os.path.join(OUTPUT_DIR, f"{file.filename}_chunks.jsonl")

        # Process the PDF and generate chunks
        num_chunks = process_pdf_chunks(file_path, output_path)

        # Return a response with the number of chunks and output file info
        return {
            "filename": file.filename,
            "chunks_processed": num_chunks,
            "output_file": output_path,
            "message": "File uploaded and processed successfully!"
        }

    except Exception as e:
        return {"error": f"Failed to upload and process file: {str(e)}"}



#uvicorn app.main:app --reload