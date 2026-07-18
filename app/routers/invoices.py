from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, require_active_status, require_role
from app.models.enums import InvoiceStatus, UserRole
from app.schemas.invoice import InvoiceCreate, InvoiceResponse, PaymentRequest
from app.schemas.pagination import PaginatedResponse, PaginationParams
from app.services.billing_service import BillingService

router = APIRouter(prefix="/invoices", tags=["invoices"])


def get_service(db: Session = Depends(get_db)) -> BillingService:
    return BillingService(db)


@router.get(
    "",
    response_model=PaginatedResponse[InvoiceResponse],
    dependencies=[Depends(require_active_status)],
)
def list_invoices(
    invoice_status: InvoiceStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(
        require_role(
            UserRole.PATIENT, UserRole.DOCTOR, UserRole.WEBSITE_ADMIN
        )
    ),
    service: BillingService = Depends(get_service),
):
    try:
        return service.list_for_actor(
            UUID(current_user["user_id"]),
            current_user["role"],
            PaginationParams(page=page, page_size=page_size),
            invoice_status,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get(
    "/{invoice_id}",
    response_model=InvoiceResponse,
    dependencies=[Depends(require_active_status)],
)
def get_invoice(
    invoice_id: UUID,
    current_user: dict = Depends(
        require_role(
            UserRole.PATIENT, UserRole.DOCTOR, UserRole.WEBSITE_ADMIN
        )
    ),
    service: BillingService = Depends(get_service),
):
    try:
        return service.get_by_id_for_actor(
            invoice_id,
            UUID(current_user["user_id"]),
            current_user["role"],
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        # Hide the existence of invoices owned by another user.
        raise HTTPException(status_code=404, detail="Invoice not found") from exc


@router.post(
    "",
    response_model=InvoiceResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_active_status)],
)
def create_invoice(
    payload: InvoiceCreate,
    current_user: dict = Depends(require_role(UserRole.WEBSITE_ADMIN)),
    service: BillingService = Depends(get_service),
):
    try:
        return service.create_invoice(
            payload,
            UUID(current_user["user_id"]),
            current_user["role"],
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/{invoice_id}/issue",
    response_model=InvoiceResponse,
    dependencies=[Depends(require_active_status)],
)
def issue_invoice(
    invoice_id: UUID,
    current_user: dict = Depends(require_role(UserRole.WEBSITE_ADMIN)),
    service: BillingService = Depends(get_service),
):
    try:
        return service.issue_invoice(
            invoice_id,
            UUID(current_user["user_id"]),
            current_user["role"],
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/{invoice_id}/pay",
    response_model=InvoiceResponse,
    dependencies=[Depends(require_active_status)],
)
def pay_invoice(
    invoice_id: UUID,
    payload: PaymentRequest,
    current_user: dict = Depends(require_role(UserRole.WEBSITE_ADMIN)),
    service: BillingService = Depends(get_service),
):
    try:
        return service.record_payment(invoice_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/{invoice_id}/cancel",
    response_model=InvoiceResponse,
    dependencies=[Depends(require_active_status)],
)
def cancel_invoice(
    invoice_id: UUID,
    current_user: dict = Depends(require_role(UserRole.WEBSITE_ADMIN)),
    service: BillingService = Depends(get_service),
):
    try:
        return service.cancel_invoice(
            invoice_id,
            UUID(current_user["user_id"]),
            current_user["role"],
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
