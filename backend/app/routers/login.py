

    
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import jwt, JWTError

from app.db import Base, engine, SessionLocal
from app.models import User
from app.schemas import UserCreate, UserOut, TokenOut
from app.crud import get_user_by_email, create_user
from app.utils.password_hash import verify_password
from app.utils.jwt_auth import create_access_token, SECRET_KEY, ALGORITHM



import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from pydantic import BaseModel

router = APIRouter()
security = HTTPBearer(auto_error=False)

from dotenv import load_dotenv
load_dotenv()  # 

# 1. Your Supabase JWT Secret (Dashboard -> Project Settings -> API)
SUPABASE_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET")
ALGORITHM = "HS256"

# 2. A simple Pydantic schema to represent the authenticated user
class AuthenticatedUser(BaseModel):
    id: str
    email: str
    username: str

# 3. The Dependency: Verifies the token and extracts user data directly from it
def current_user(creds: HTTPAuthorizationCredentials = Depends(security)) -> AuthenticatedUser:
    if not creds or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing bearer token")

    try:
        # Decode the token cryptographically 
        payload = jwt.decode(
            creds.credentials, 
            SUPABASE_JWT_SECRET, 
            algorithms=[ALGORITHM],
            audience="authenticated"
        )
    except JWTError as e:
        print(f"JWT Error: {e}") 
        raise HTTPException(status_code=401, detail="Invalid or expired Supabase token")

    # Extract the user's UUID
    uid = payload.get("sub")
    if not uid:
        raise HTTPException(status_code=401, detail="Token does not contain a valid user ID")

    # Extract email and the custom username we saved during frontend signup
    email = payload.get("email", "")
    user_metadata = payload.get("user_metadata", {})
    username = user_metadata.get("username", "")

    # Return the Pydantic model. No database lookup required!
    return AuthenticatedUser(id=uid, email=email, username=username)

# 4. Your Protected Route(s)
@router.get("/auth/me", response_model=AuthenticatedUser)
def me(user: AuthenticatedUser = Depends(current_user)):
    """
    Any route that uses `Depends(current_user)` is automatically protected.
    If the token is invalid, it throws a 401 before this code ever runs.
    """
    print(f"Successfully verified user: {user.email} (ID: {user.id})")  
    return user