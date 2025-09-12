

    
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



router = APIRouter()


Base.metadata.create_all(bind=engine)  # For dev; use Alembic in real apps

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

security = HTTPBearer(auto_error=False)

@router.post("/register", response_model=UserOut, status_code=201)
def register(body: UserCreate, db: Session = Depends(get_db)):
    if get_user_by_email(db, body.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    user = create_user(db, body.email, body.password)
    return user

@router.post("/token", response_model=TokenOut)
def login(body: UserCreate, db: Session = Depends(get_db)):
    user = get_user_by_email(db, body.email)
    if not user or not verify_password(body.password, user.password_hash) or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(sub=str(user.id))
    return {"access_token": token, "token_type": "bearer"}

def current_user(creds: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)) -> User:
    if not creds or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing bearer token")

    try:
        payload = jwt.decode(creds.credentials, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    # Ensure the token contains a valid user ID (sub)
    uid = payload.get("sub")
    if not uid:
        raise HTTPException(status_code=401, detail="Token does not contain a valid user ID")

    # Retrieve user from the database
    user = db.get(User, int(uid)) if uid is not None else None
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return user

@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    print(f"Authenticated user: {user.email}")  # Debug print
    return user
