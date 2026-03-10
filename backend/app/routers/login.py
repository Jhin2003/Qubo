from fastapi import APIRouter, Depends, HTTPException, status
# Removed: security (HTTPBearer) and jwt (jose) imports

from sqlalchemy.orm import Session

from app.db import Base, engine, SessionLocal
from app.models import User
# Removed: TokenOut from schemas (no longer generating tokens)
from app.schemas import UserCreate, UserOut 
from app.crud import get_user_by_email, create_user
from app.utils.password_hash import verify_password
# Removed: jwt_auth imports (create_access_token, keys, etc.)
from supabase import create_client, Client

import os
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from supabase import create_client, Client

from dotenv import load_dotenv

# Your other imports (routers, etc.) go here...
# from app.routers import chat, file_upload, login

# 1. Force Python to read the .env file immediately


router = APIRouter()

load_dotenv()

# Initialize Supabase client
# Ensure you set these in your Render environment variables or local .env
SUPABASE_URL =os.environ.get("SUPABASE_URL")
SUPABASE_KEY =os.environ.get("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Define your expected request body
class UserCreate(BaseModel):
    email: str
    password: str
    username: str = None # Optional

@router.post("/register", status_code=201)
def register(body: UserCreate):
    try:
        # Supabase creates the user, hashes the password, and stores it in its secure auth.users table
        response = supabase.auth.sign_up({
            "email": body.email,
            "password": body.password,
            "options": {
                # Store extra metadata like username here
                "data": {"username": body.username} 
            }
        })
        return {"message": "User registered successfully", "user": response.user}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/login")
def login(body: UserCreate):
    try:
        # Verifies credentials and automatically returns a secure session with a JWT
        response = supabase.auth.sign_in_with_password({
            "email": body.email,
            "password": body.password
        })
        
        # You now have an access token you can use to secure your RAG endpoints!
        return {
            "message": "Login successful",
            "access_token": response.session.access_token,
            "user": response.user
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid credentials")

# We replace /users/{user_id} with /auth/me to fetch the currently logged-in user
# using the token they receive upon login.
@router.get("/auth/me")
def get_user_details(token: str):
    try:
        # Supabase verifies the token and returns the corresponding user data
        response = supabase.auth.get_user(token)
        return response.user
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid or expired token")