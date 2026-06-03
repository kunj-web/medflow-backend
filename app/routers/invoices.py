from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, get_current_user, require_role
from app.models.enums import InvoiceStatus, UserRole
from app.models.user import User
from app.services.billing_service import BillingService
from app.schemas.invoice import (
    InvoiceCreate,
    InvoiceResponse,
    PaymentRequest,
)
from app.schemas.pagination import PaginatedResponse, PaginationParams

router = APIRouter(prefix="/invoices", tags=["invoices"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_service(db: Session = Depends(get_db)) -> BillingService:
    return BillingService(db)


def _hospital_id(current_user: User) -> UUID:
    return current_user.hospital_id


# ---------------------------------------------------------------------------
# List & get
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=PaginatedResponse[InvoiceResponse],
    summary="List invoices (admin / staff)",
)
def list_invoices(
    patient_id: Optional[UUID] = Query(None),
    invoice_status: Optional[InvoiceStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.STAFF)),
    service: BillingService = Depends(get_service),
):
    params = PaginationParams(page=page, page_size=page_size)
    return service.list_invoices(
        _hospital_id(current_user), params, patient_id, invoice_status
    )


@router.get(
    "/{invoice_id}",
    response_model=InvoiceResponse,
    summary="Get an invoice by ID",
)
def get_invoice(
    invoice_id: UUID,
    current_user: User = Depends(get_current_user),
    service: BillingService = Depends(get_service),
):
    """
    Patients can only see their own invoices.
    Admin / staff / doctor can see any invoice in the hospital.
    """
    try:
        invoice = service.get_by_id(_hospital_id(current_user), invoice_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    if current_user.role == UserRole.PATIENT:
        patient = getattr(current_user, "patient", None)
        if not patient or invoice.patient_id != patient.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return invoice


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=InvoiceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a draft invoice for an appointment (admin / staff)",
)
def create_invoice(
    payload: InvoiceCreate,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.STAFF)),
    service: BillingService = Depends(get_service),
):
    try:
        return service.create_invoice(_hospital_id(current_user), payload)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


# ---------------------------------------------------------------------------
# State transitions
# ---------------------------------------------------------------------------

@router.post(
    "/{invoice_id}/issue",
    response_model=InvoiceResponse,
    summary="Issue a draft invoice (admin / staff)",
)
def issue_invoice(
    invoice_id: UUID,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.STAFF)),
    service: BillingService = Depends(get_service),
):
    try:
        return service.issue_invoice(_hospital_id(current_user), invoice_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post(
    "/{invoice_id}/pay",
    response_model=InvoiceResponse,
    summary="Record a payment against an invoice (admin / staff)",
)
def pay_invoice(
    invoice_id: UUID,
    payload: PaymentRequest,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.STAFF)),
    service: BillingService = Depends(get_service),
):
    try:
        return service.record_payment(_hospital_id(current_user), invoice_id, payload)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.post(
    "/{invoice_id}/cancel",
    response_model=InvoiceResponse,
    summary="Cancel an invoice (admin only)",
)
def cancel_invoice(
    invoice_id: UUID,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    service: BillingService = Depends(get_service),
):
    try:
        return service.cancel_invoice(_hospital_id(current_user), invoice_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))