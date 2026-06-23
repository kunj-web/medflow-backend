from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from app.models.enums import Gender, WorkType


class PublicHospitalResponse(BaseModel):
    id: UUID
    name: str
    city: str | None
    state: str | None
    address: str | None
    logo_url: str | None

    model_config = {"from_attributes": True}


class PublicDoctorResponse(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    gender: Gender
    specialization: str
    qualification: str | None
    experience_years: int
    consultation_fee: float
    work_type: WorkType
    hospital_id: UUID | None
    hospital_name: str | None
    city: str | None
    clinic_name: str | None


class PublicDoctorSearchResponse(BaseModel):
    data: list[PublicDoctorResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class PublicHospitalListResponse(BaseModel):
    data: list[PublicHospitalResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
