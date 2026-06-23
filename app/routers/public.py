from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.schemas.pagination import PaginationParams
from app.schemas.public import PublicDoctorSearchResponse, PublicHospitalListResponse
from app.services.public_service import PublicService

router = APIRouter(prefix="/public", tags=["public"])


def get_service(db: Session = Depends(get_db)) -> PublicService:
    return PublicService(db)


@router.get("/doctors/search", response_model=PublicDoctorSearchResponse)
def search_doctors(
    city: str | None = Query(None),
    specialization: str | None = Query(None),
    hospital_id: UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: PublicService = Depends(get_service),
):
    return service.search_doctors(
        PaginationParams(page=page, page_size=page_size),
        city=city,
        specialization=specialization,
        hospital_id=hospital_id,
    )


@router.get("/hospitals", response_model=PublicHospitalListResponse)
def list_hospitals(
    city: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: PublicService = Depends(get_service),
):
    return service.list_hospitals(
        PaginationParams(page=page, page_size=page_size),
        city=city,
        search=search,
    )
