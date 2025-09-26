# security.py
import os
from passlib.context import CryptContext

# Argon2id is strong & memory-hard
pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
    # You can tune Argon2 params via PASSLIB_* env vars if needed
)

# Optional pepper (extra secret) pulled from env; keep short and rotateable
PEPPER = os.getenv("PASSWORD_PEPPER", "")

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain + PEPPER)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain + PEPPER, hashed)
