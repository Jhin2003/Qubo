from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import chat, file_upload, login
from app.services.loaders import warmup

from dotenv import load_dotenv
load_dotenv() 

@asynccontextmanager
async def lifespan(app: FastAPI):
   
    warmup()
    yield

app = FastAPI(lifespan=lifespan)

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
app.include_router(login.router)

# Dev
# uvicorn app.main:app --reload

#prod
#uvicorn app.main:app --host 0.0.0.0 --port $PORT