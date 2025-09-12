# crud.py
from sqlalchemy.orm import Session
from app.models import User
from .utils.password_hash import hash_password

def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email.lower().strip()).first()

def create_user(db: Session, email: str, password: str) -> User:
    user = User(email=email.lower().strip(), password_hash=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
