from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"


# ─── Password ────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ─── Tokens ──────────────────────────────────────────────────────────────────

def create_access_token(payload: dict) -> str:
    data = payload.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    data.update({"exp": expire, "type": "access"})
    return jwt.encode(data, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(payload: dict) -> str:
    data = payload.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    data.update({"exp": expire, "type": "refresh"})
    return jwt.encode(data, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def create_token_pair(user_id: str, role: str, hospital_id: str) -> dict:
    payload = {
        "sub": user_id,
        "role": role,
        "hospital_id": hospital_id,
    }
    return {
        "access_token": create_access_token(payload),
        "refresh_token": create_refresh_token(payload),
        "token_type": "bearer",
    }