import jwt
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Request, HTTPException, status
from config import settings

def create_session_token(user_id: str) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(days=1),
    }
    return jwt.encode(payload, settings.SESSION_SECRET, algorithm="HS256")

def decode_session_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, settings.SESSION_SECRET, algorithms=["HS256"])
        return payload.get("user_id")
    except jwt.PyJWTError:
        return None
