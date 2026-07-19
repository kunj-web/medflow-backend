from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, require_active_status, require_role
from app.models.enums import UserRole
from app.schemas.search import SearchResponse
from app.services.search_service import SearchService

router = APIRouter(prefix="/search", tags=["search"])


@router.get(
    "",
    response_model=SearchResponse,
    dependencies=[Depends(require_active_status)],
)
def global_search(
    q: str = Query(..., min_length=2, max_length=100),
    current_user: dict = Depends(
        require_role(UserRole.PATIENT, UserRole.DOCTOR, UserRole.WEBSITE_ADMIN)
    ),
    db: Session = Depends(get_db),
):
    return SearchService(db).search(
        q,
        UUID(current_user["user_id"]),
        current_user["role"],
    )
