from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


# ─── Password ────────────────────────────────────────────────────────────


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ─── Tokens ──────────────────────────────────────────────────────────────


def create_access_token(payload: dict) -> str:
    data = payload.copy()
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    data.update({"exp": expire, "type": "access"})
    return jwt.encode(data, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token(payload: dict) -> str:
    data = payload.copy()
    expire = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    data.update({"exp": expire, "type": "refresh"})
    return jwt.encode(data, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        return payload
    except JWTError:
        return None


def create_token_pair(
    user_id: str,
    role: str,
    status: str,
    is_super_admin: bool = False,
) -> dict:
    """
    Token payload no longer includes hospital_id — users are not
    hospital-scoped under the marketplace model.

    status and is_super_admin are embedded for fast access-control checks
    without a DB round-trip on every request. This means status changes
    (e.g. a doctor being approved/rejected) only take effect on next
    login/refresh, not immediately — acceptable given short-lived access
    tokens (see settings.access_token_expire_minutes).
    """
    payload = {
        "sub": user_id,
        "role": role,
        "status": status,
        "is_super_admin": is_super_admin,
    }
    return {
        "access_token": create_access_token(payload),
        "refresh_token": create_refresh_token(payload),
        "token_type": "bearer",
        "role": role,
        "status": status,
        "is_super_admin": is_super_admin,
    }
