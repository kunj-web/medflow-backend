from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import SessionLocal
from app.models.enums import AccountStatus, UserRole

bearer_scheme = HTTPBearer()


# ─── Database ──────────────────────────────────────────────────────────


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DBSession = Annotated[Session, Depends(get_db)]


# ─── Auth ──────────────────────────────────────────────────────────────


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """
    Returns the authenticated user as a plain dict, decoded from the JWT.
    No hospital_id — users are not hospital-scoped under the marketplace
    model. status and is_super_admin come from the token (see
    core/security.create_token_pair for why these are embedded rather
    than looked up fresh).
    """
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
        "status": payload.get("status"),
        "is_super_admin": payload.get("is_super_admin", False),
    }


CurrentUser = Annotated[dict, Depends(get_current_user)]


# ─── Role Guards ───────────────────────────────────────────────────────


def require_role(*roles: UserRole):
    """
    Usage:
        @router.get("/admin/only")
        def admin_route(user=Depends(require_role(UserRole.WEBSITE_ADMIN))):
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


def require_active_status(current_user: dict = Depends(get_current_user)) -> dict:
    """
    Ensures the user's account is ACTIVE (approved), not PENDING or
    REJECTED. Use on any route a pending/rejected doctor should not be
    able to reach (e.g. booking-related write actions), even though
    login itself already blocks non-ACTIVE users from getting a token
    in the first place — this is a defense-in-depth check for routes
    reachable with an older still-valid token issued before a status
    change took effect.
    """
    if current_user.get("status") != AccountStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not active",
        )
    return current_user


def require_super_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Ensures the user is the bootstrapped super admin."""
    if not current_user.get("is_super_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required",
        )
    return current_user
