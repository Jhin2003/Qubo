from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import chat, file_upload

app = FastAPI()

# Allow CORS for all origins (for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the routers
app.include_router(chat.router)
app.include_router(file_upload.router)



#uvicorn app.main:app --reload