from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, field_validator

from app.models.enums import InvoiceStatus
from app.schemas.validators.common import validate_positive_amount, validate_non_empty_string


# ---------------------------------------------------------------------------
# Line items (embedded in invoice, not a separate DB table)
# ---------------------------------------------------------------------------

class InvoiceLineItem(BaseModel):
    description: str
    quantity: int = 1
    unit_price: float
    amount: float          # quantity × unit_price, validated server-side

    @field_validator("description")
    @classmethod
    def non_empty(cls, v: str) -> str:
        return validate_non_empty_string(v)

    @field_validator("unit_price", "amount")
    @classmethod
    def positive(cls, v: float) -> float:
        return validate_positive_amount(v)

    @field_validator("quantity")
    @classmethod
    def at_least_one(cls, v: int) -> int:
        if v < 1:
            raise ValueError("quantity must be at least 1")
        return v


# ---------------------------------------------------------------------------
# Invoice
# ---------------------------------------------------------------------------

class InvoiceCreate(BaseModel):
    appointment_id: UUID
    line_items: list[InvoiceLineItem]
    discount_amount: float = 0.0
    notes: Optional[str] = None

    @field_validator("line_items")
    @classmethod
    def at_least_one_item(cls, v: list[InvoiceLineItem]) -> list[InvoiceLineItem]:
        if not v:
            raise ValueError("invoice must have at least one line item")
        return v

    @field_validator("discount_amount")
    @classmethod
    def non_negative_discount(cls, v: float) -> float:
        if v < 0:
            raise ValueError("discount_amount cannot be negative")
        return v


class PaymentRequest(BaseModel):
    amount_paid: float
    payment_method: str          # "cash" | "card" | "upi" | "insurance"
    transaction_reference: Optional[str] = None

    @field_validator("amount_paid")
    @classmethod
    def positive_payment(cls, v: float) -> float:
        return validate_positive_amount(v)

    @field_validator("payment_method")
    @classmethod
    def valid_method(cls, v: str) -> str:
        allowed = {"cash", "card", "upi", "insurance"}
        if v.lower() not in allowed:
            raise ValueError(f"payment_method must be one of {allowed}")
        return v.lower()


class InvoiceResponse(BaseModel):
    id: UUID
    invoice_number: str          # e.g. "INV-2025-00042"
    appointment_id: UUID
    patient_id: UUID
    status: InvoiceStatus
    line_items: list[InvoiceLineItem]
    subtotal: float
    discount_amount: float
    total_amount: float
    amount_paid: float
    balance_due: float
    payment_method: Optional[str]
    transaction_reference: Optional[str]
    notes: Optional[str]
    issued_at: Optional[datetime]
    paid_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}