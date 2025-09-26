from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from .jwt_auth import verify_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = verify_access_token(token)
        return payload  # You can return the user data or any other info from the token
    except HTTPException as e:
        raise e
