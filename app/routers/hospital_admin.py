from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, require_role
from app.models.enums import UserRole
from app.models.hospital import Hospital, HospitalFeature
from app.schemas.hospital import (
    FeatureResponse,
    FeatureToggle,
    HospitalResponse,
    HospitalUpdate,
)
from app.services.storage_service import storage_service

router = APIRouter(prefix="/admin/hospital", tags=["hospital admin"])

ALLOWED_LOGO_TYPES = {"image/png", "image/jpeg"}
MAX_LOGO_BYTES = 2 * 1024 * 1024  # 2 MB


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_hospital_or_404(db: Session, hospital_id: UUID) -> Hospital:
    hospital = (
        db.query(Hospital)
        .filter(Hospital.id == hospital_id, Hospital.deleted_at.is_(None))
        .first()
    )
    if not hospital:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hospital not found")
    return hospital


def _extract_object_key(logo_url: str) -> str | None:
    """
    Derive the S3 object key from a Supabase public URL.

    URL format:
        {SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{object_key}

    Returns the object_key portion, or None if the URL is malformed.
    """
    marker = "/object/public/"
    idx = logo_url.find(marker)
    if idx == -1:
        return None
    after_marker = logo_url[idx + len(marker):]
    slash = after_marker.find("/")
    if slash == -1:
        return None
    return after_marker[slash + 1:]


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=HospitalResponse,
    summary="Get hospital config (admin only)",
)
def get_hospital(
    current_user: dict = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    return HospitalResponse.model_validate(
        _get_hospital_or_404(db, UUID(current_user["hospital_id"]))
    )


# ---------------------------------------------------------------------------
# Update config
# ---------------------------------------------------------------------------

@router.put(
    "",
    response_model=HospitalResponse,
    summary="Update hospital config / branding (admin only)",
)
def update_hospital(
    payload: HospitalUpdate,
    current_user: dict = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    hospital = _get_hospital_or_404(db, UUID(current_user["hospital_id"]))
    update_data = payload.model_dump(exclude_unset=True)

    # logo_url is set only via the /logo endpoint — never accepted here
    update_data.pop("logo_url", None)

    for field, value in update_data.items():
        # HttpUrl → str coercion for website field
        setattr(hospital, field, str(value) if hasattr(value, "__str__") and field == "website" else value)

    db.commit()
    db.refresh(hospital)
    return HospitalResponse.model_validate(hospital)


# ---------------------------------------------------------------------------
# Logo upload
# ---------------------------------------------------------------------------

@router.post(
    "/logo",
    response_model=HospitalResponse,
    summary="Upload or replace the hospital logo (admin only)",
)
async def upload_logo(
    file: UploadFile = File(...),
    current_user: dict = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    hospital_id = UUID(current_user["hospital_id"])
    hospital = _get_hospital_or_404(db, hospital_id)

    # Delete the old logo from storage if one exists.
    # Done before upload so an extension change (PNG → JPEG) doesn't
    # leave an orphan file in the bucket.
    if hospital.logo_url:
        old_key = _extract_object_key(hospital.logo_url)
        if old_key:
            storage_service.delete_file(old_key)

    # upload_logo validates MIME type and size, raises HTTPException on failure
    logo_url = await storage_service.upload_logo(
        hospital_id=str(hospital_id),
        file=file,
    )

    hospital.logo_url = logo_url
    db.commit()
    db.refresh(hospital)
    return HospitalResponse.model_validate(hospital)


# ---------------------------------------------------------------------------
# Logo delete
# ---------------------------------------------------------------------------

@router.delete(
    "/logo",
    response_model=HospitalResponse,
    summary="Delete the hospital logo (admin only)",
)
def delete_logo(
    current_user: dict = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    hospital_id = UUID(current_user["hospital_id"])
    hospital = _get_hospital_or_404(db, hospital_id)

    if not hospital.logo_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No logo is currently set for this hospital.",
        )

    object_key = _extract_object_key(hospital.logo_url)
    if object_key:
        storage_service.delete_file(object_key)

    hospital.logo_url = None
    db.commit()
    db.refresh(hospital)
    return HospitalResponse.model_validate(hospital)


# ---------------------------------------------------------------------------
# Feature flags
# ---------------------------------------------------------------------------

@router.post(
    "/features",
    response_model=FeatureResponse,
    summary="Enable or disable a feature flag (admin only)",
)
def toggle_feature(
    payload: FeatureToggle,
    current_user: dict = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    feature = (
        db.query(HospitalFeature)
        .filter(
            HospitalFeature.hospital_id == UUID(current_user["hospital_id"]),
            HospitalFeature.feature_key == payload.feature_key,
        )
        .first()
    )

    if feature:
        feature.is_enabled = payload.is_enabled
    else:
        feature = HospitalFeature(
            hospital_id=UUID(current_user["hospital_id"]),
            feature_key=payload.feature_key,
            is_enabled=payload.is_enabled,
        )
        db.add(feature)

    db.commit()
    db.refresh(feature)
    return FeatureResponse.model_validate(feature)
