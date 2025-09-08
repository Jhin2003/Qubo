from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import chat, file_upload
from app.services.loaders import warmup

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once per worker when the process starts
    warmup()
    yield
    # optional: shutdown cleanup here

app = FastAPI(lifespan=lifespan)

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

# Run:
# uvicorn app.main:app --reload
