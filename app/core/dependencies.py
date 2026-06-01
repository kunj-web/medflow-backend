from typing import Generator, Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.core.security import decode_token
from app.models.enums import UserRole

bearer_scheme = HTTPBearer()


# ─── Database ─────────────────────────────────────────────────────────────────

def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DBSession = Annotated[Session, Depends(get_db)]


# ─── Auth ─────────────────────────────────────────────────────────────────────

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    token = credentials.credentials
    payload = decode_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    return {
        "user_id": payload.get("sub"),
        "role": payload.get("role"),
        "hospital_id": payload.get("hospital_id"),
    }


CurrentUser = Annotated[dict, Depends(get_current_user)]


# ─── Role Guards ──────────────────────────────────────────────────────────────

def require_role(*roles: UserRole):
    """
    Usage:
        @router.get("/admin/only")
        def admin_route(user=Depends(require_role(UserRole.ADMIN))):
            ...
    """
    def checker(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user["role"] not in [r.value for r in roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {[r.value for r in roles]}",
            )
        return current_user

    return checker


def require_same_hospital(current_user: dict = Depends(get_current_user)) -> dict:
    """Ensures user can only access their own hospital's data."""
    if not current_user.get("hospital_id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hospital context required",
        )
    return current_user