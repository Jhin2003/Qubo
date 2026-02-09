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

router = APIRouter()

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Removed: security = HTTPBearer(auto_error=False)

@router.post("/register", response_model=UserOut, status_code=201)
def register(body: UserCreate, db: Session = Depends(get_db)):
    if get_user_by_email(db, body.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    user = create_user(db, body.username, body.email, body.password)
    return user

# Renamed "/token" to "/login"
# Changed return type from TokenOut to UserOut
@router.post("/login", response_model=UserOut)
def login(body: UserCreate, db: Session = Depends(get_db)):
    user = get_user_by_email(db, body.email)
    
    # Verify password still happens, but we don't generate a token
    if not user or not verify_password(body.password, user.password_hash) or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Removed: token = create_access_token(...)
    
    # Just return the user object to confirm login was successful
    return user 

# Removed: def current_user(...) dependency function

# Renamed "/auth/me" to "/users/{user_id}"
# Since we don't have a token, we must ask for the ID explicitly
@router.get("/users/{user_id}", response_model=UserOut)
def get_user_details(user_id: int, db: Session = Depends(get_db)):
    # Direct database lookup instead of decoding a token
    user = db.get(User, user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    print(f"Retrieved user: {user.email}")  
    return user