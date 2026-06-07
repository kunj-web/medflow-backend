from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.enums import AppointmentStatus, InvoiceStatus
from app.models.invoice import Invoice
from app.schemas.invoice import (
    InvoiceCreate,
    InvoiceResponse,
    PaymentRequest,
)
from app.schemas.pagination import PaginatedResponse, PaginationParams


class BillingService:

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Invoice creation
    # ------------------------------------------------------------------

    def create_invoice(
        self, hospital_id: UUID, payload: InvoiceCreate
    ) -> InvoiceResponse:
        """
        Issue a draft invoice against an appointment.

        Rules:
        - Appointment must exist, belong to this hospital, and not be cancelled.
        - One invoice per appointment (no duplicates).
        - Subtotal, total, and balance are all computed here — never trusted
          from the client.
        """
        appointment = self._get_appointment_or_404(hospital_id, payload.appointment_id)

        if appointment.status == AppointmentStatus.CANCELLED:
            raise ValueError("Cannot invoice a cancelled appointment")

        existing = self._get_invoice_by_appointment(payload.appointment_id)
        if existing:
            raise ValueError("An invoice already exists for this appointment")

        subtotal = sum(
            item.quantity * item.unit_price for item in payload.line_items
        )
        # Validate that caller-supplied amounts match computed amounts
        for item in payload.line_items:
            expected = round(item.quantity * item.unit_price, 2)
            if round(item.amount, 2) != expected:
                raise ValueError(
                    f"Line item '{item.description}': amount {item.amount} does not "
                    f"match quantity × unit_price ({expected})"
                )

        total = max(0.0, round(subtotal - payload.discount_amount, 2))

        invoice_number = self._generate_invoice_number(hospital_id)

        invoice = Invoice(
            hospital_id=hospital_id,
            appointment_id=appointment.id,
            patient_id=appointment.patient_id,
            invoice_number=invoice_number,
            status=InvoiceStatus.DRAFT,
            line_items=[item.model_dump() for item in payload.line_items],
            subtotal=round(subtotal, 2),
            discount_amount=round(payload.discount_amount, 2),
            total_amount=total,
            amount_paid=0.0,
            balance_due=total,
            notes=payload.notes,
        )
        self.db.add(invoice)
        self.db.commit()
        self.db.refresh(invoice)
        return self._to_response(invoice)

    # ------------------------------------------------------------------
    # Issue (draft → issued)
    # ------------------------------------------------------------------

    def issue_invoice(self, hospital_id: UUID, invoice_id: UUID) -> InvoiceResponse:
        invoice = self._get_or_404(hospital_id, invoice_id)

        if invoice.status != InvoiceStatus.DRAFT:
            raise ValueError(f"Invoice is already {invoice.status.value}")

        invoice.status = InvoiceStatus.ISSUED
        invoice.issued_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(invoice)
        return self._to_response(invoice)

    # ------------------------------------------------------------------
    # Payment
    # ------------------------------------------------------------------

    def record_payment(
        self, hospital_id: UUID, invoice_id: UUID, payload: PaymentRequest
    ) -> InvoiceResponse:
        """
        Record a payment against an issued invoice.

        - Allows partial payments (balance_due tracks remaining amount).
        - Overpayment is rejected.
        - Once balance_due reaches 0 the invoice is marked PAID.
        """
        invoice = self._get_or_404(hospital_id, invoice_id)

        if invoice.status == InvoiceStatus.DRAFT:
            raise ValueError("Cannot accept payment for a draft invoice — issue it first")

        if invoice.status == InvoiceStatus.PAID:
            raise ValueError("Invoice is already fully paid")

        if invoice.status == InvoiceStatus.CANCELLED:
            raise ValueError("Cannot accept payment for a cancelled invoice")

        if round(payload.amount_paid, 2) > round(float(invoice.balance_due), 2):
            raise ValueError(
                f"Payment amount {payload.amount_paid} exceeds balance due "
                f"{invoice.balance_due}"
            )

        invoice.amount_paid = round(float(invoice.amount_paid) + float(payload.amount_paid), 2)
        invoice.balance_due = round(float(invoice.total_amount) - float(invoice.amount_paid), 2)
        invoice.payment_method = payload.payment_method
        invoice.transaction_reference = payload.transaction_reference

        if invoice.balance_due <= 0:
            invoice.status = InvoiceStatus.PAID
            invoice.paid_at = datetime.now(UTC)
            invoice.balance_due = 0.0

        self.db.commit()
        self.db.refresh(invoice)
        return self._to_response(invoice)

    # ------------------------------------------------------------------
    # Cancel invoice
    # ------------------------------------------------------------------

    def cancel_invoice(self, hospital_id: UUID, invoice_id: UUID) -> InvoiceResponse:
        invoice = self._get_or_404(hospital_id, invoice_id)

        if invoice.status == InvoiceStatus.PAID:
            raise ValueError("Cannot cancel a fully paid invoice")

        invoice.status = InvoiceStatus.CANCELLED
        self.db.commit()
        self.db.refresh(invoice)
        return self._to_response(invoice)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_by_id(self, hospital_id: UUID, invoice_id: UUID) -> InvoiceResponse:
        invoice = self._get_or_404(hospital_id, invoice_id)
        return self._to_response(invoice)

    def list_invoices(
        self,
        hospital_id: UUID,
        params: PaginationParams,
        patient_id: UUID | None = None,
        status: InvoiceStatus | None = None,
    ) -> PaginatedResponse[InvoiceResponse]:
        q = self.db.query(Invoice).filter(
            Invoice.hospital_id == hospital_id,
            Invoice.deleted_at.is_(None),
        )
        if patient_id:
            q = q.filter(Invoice.patient_id == patient_id)
        if status:
            q = q.filter(Invoice.status == status)

        total = q.count()
        invoices = (
            q.order_by(Invoice.created_at.desc())
            .offset((params.page - 1) * params.page_size)
            .limit(params.page_size)
            .all()
        )
        return PaginatedResponse(
            items=[self._to_response(inv) for inv in invoices],
            total=total,
            page=params.page,
            page_size=params.page_size,
        )

    # ------------------------------------------------------------------
    # Invoice number generation
    # ------------------------------------------------------------------

    def _generate_invoice_number(self, hospital_id: UUID) -> str:
        """
        Generate a sequential, year-scoped invoice number:
            INV-{YYYY}-{SEQ:05d}
        e.g. INV-2025-00001, INV-2025-00042

        Uses a DB-level COUNT to determine the next sequence number within
        the current year for this hospital. This is safe under normal load;
        for high-concurrency environments consider a Postgres SEQUENCE instead.
        """
        year = datetime.now(UTC).year
        year_start = datetime(year, 1, 1, tzinfo=UTC)

        count = (
            self.db.query(func.count(Invoice.id))
            .filter(
                Invoice.hospital_id == hospital_id,
                Invoice.created_at >= year_start,
            )
            .scalar()
            or 0
        )
        seq = count + 1
        return f"INV-{year}-{seq:05d}"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_404(self, hospital_id: UUID, invoice_id: UUID) -> Invoice:
        invoice = (
            self.db.query(Invoice)
            .filter(
                Invoice.id == invoice_id,
                Invoice.hospital_id == hospital_id,
                Invoice.deleted_at.is_(None),
            )
            .first()
        )
        if not invoice:
            raise LookupError("Invoice not found")
        return invoice

    def _get_invoice_by_appointment(self, appointment_id: UUID) -> Invoice | None:
        return (
            self.db.query(Invoice)
            .filter(
                Invoice.appointment_id == appointment_id,
                Invoice.deleted_at.is_(None),
            )
            .first()
        )

    def _get_appointment_or_404(
        self, hospital_id: UUID, appointment_id: UUID
    ) -> Appointment:
        appointment = (
            self.db.query(Appointment)
            .filter(
                Appointment.id == appointment_id,
                Appointment.hospital_id == hospital_id,
                Appointment.deleted_at.is_(None),
            )
            .first()
        )
        if not appointment:
            raise LookupError("Appointment not found")
        return appointment

    def _to_response(self, invoice: Invoice) -> InvoiceResponse:
        from app.schemas.invoice import InvoiceLineItem
        line_items = [InvoiceLineItem(**item) for item in (invoice.line_items or [])]
        return InvoiceResponse(
            id=invoice.id,
            invoice_number=invoice.invoice_number,
            appointment_id=invoice.appointment_id,
            patient_id=invoice.patient_id,
            status=invoice.status,
            line_items=line_items,
            subtotal=invoice.subtotal,
            discount_amount=invoice.discount_amount,
            total_amount=invoice.total_amount,
            amount_paid=invoice.amount_paid,
            balance_due=invoice.balance_due,
            payment_method=invoice.payment_method,
            transaction_reference=invoice.transaction_reference,
            notes=invoice.notes,
            issued_at=invoice.issued_at,
            paid_at=invoice.paid_at,
            created_at=invoice.created_at,
        )
