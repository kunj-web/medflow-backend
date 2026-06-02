from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from app.core.dependencies import get_db
from app.models.hospital import Hospital, HospitalFeature
from pydantic import BaseModel
from typing import Optional, Dict
from uuid import UUID

router = APIRouter(prefix="/config", tags=["Config"])


class HospitalConfigResponse(BaseModel):
    hospital: dict
    features: Dict[str, bool]

    model_config = {"from_attributes": True}


@router.get("/hospital/{hospital_id}")
def get_hospital_config(hospital_id: UUID, db: Session = Depends(get_db)):
    """
    Public endpoint — no auth required.
    Frontend calls this on load to get branding, config, and enabled features.
    Mobile app calls the same endpoint.
    """
    hospital = (
        db.query(Hospital)
        .options(joinedload(Hospital.features))
        .filter(
            Hospital.id == hospital_id,
            Hospital.is_active == True,
            Hospital.deleted_at.is_(None),
        )
        .first()
    )

    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    features = {f.feature_key: f.is_enabled for f in hospital.features}

    return {
        "hospital": {
            "id": str(hospital.id),
            "name": hospital.name,
            "logo_url": hospital.logo_url,
            "primary_color": hospital.primary_color,
            "secondary_color": hospital.secondary_color,
            "address": hospital.address,
            "phone": hospital.phone,
            "email": hospital.email,
            "currency": hospital.currency,
            "timezone": hospital.timezone,
        },
        "features": features,
    }