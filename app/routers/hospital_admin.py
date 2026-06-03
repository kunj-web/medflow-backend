from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, require_role
from app.models.enums import UserRole
from app.models.user import User
from app.models.hospital import Hospital, HospitalFeature
from app.schemas.hospital import (
    FeatureToggle,
    FeatureResponse,
    HospitalResponse,
    HospitalUpdate,
)

router = APIRouter(prefix="/admin/hospital", tags=["hospital admin"])

ALLOWED_LOGO_TYPES = {"image/png", "image/jpeg", "image/webp", "image/svg+xml"}
MAX_LOGO_BYTES = 2 * 1024 * 1024  # 2 MB


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_db_session(db: Session = Depends(get_db)) -> Session:
    return db


def _get_hospital_or_404(db: Session, hospital_id: UUID) -> Hospital:
    hospital = (
        db.query(Hospital)
        .filter(Hospital.id == hospital_id, Hospital.deleted_at.is_(None))
        .first()
    )
    if not hospital:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hospital not found")
    return hospital


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=HospitalResponse,
    summary="Get hospital config (admin only)",
)
def get_hospital(
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    return HospitalResponse.model_validate(
        _get_hospital_or_404(db, current_user.hospital_id)
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
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    hospital = _get_hospital_or_404(db, current_user.hospital_id)
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
    summary="Upload a hospital logo to Cloudflare R2 (admin only)",
)
async def upload_logo(
    file: UploadFile = File(...),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    # Validate content type
    if file.content_type not in ALLOWED_LOGO_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{file.content_type}'. "
                   f"Allowed: {', '.join(ALLOWED_LOGO_TYPES)}",
        )

    contents = await file.read()
    if len(contents) > MAX_LOGO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Logo must be under 2 MB",
        )

    # Upload via storage_service (imported lazily to keep router thin)
    try:
        from app.services.storage_service import StorageService
        storage = StorageService()
        logo_url = await storage.upload_logo(
            hospital_id=current_user.hospital_id,
            data=contents,
            content_type=file.content_type,
            filename=file.filename or "logo",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Logo upload failed: {exc}",
        )

    hospital = _get_hospital_or_404(db, current_user.hospital_id)
    hospital.logo_url = logo_url
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
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    feature = (
        db.query(HospitalFeature)
        .filter(
            HospitalFeature.hospital_id == current_user.hospital_id,
            HospitalFeature.feature_key == payload.feature_key,
        )
        .first()
    )

    if feature:
        feature.is_enabled = payload.is_enabled
    else:
        feature = HospitalFeature(
            hospital_id=current_user.hospital_id,
            feature_key=payload.feature_key,
            is_enabled=payload.is_enabled,
        )
        db.add(feature)

    db.commit()
    db.refresh(feature)
    return FeatureResponse.model_validate(feature)