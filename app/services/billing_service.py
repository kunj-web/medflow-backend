from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.enums import AppointmentStatus, InvoiceStatus, UserRole
from app.models.invoice import Invoice
from app.models.patient import Patient
from app.schemas.invoice import InvoiceCreate, InvoiceResponse, PaymentRequest
from app.schemas.pagination import PaginatedResponse, PaginationParams
from app.services.audit_log_service import AuditLogService


class BillingService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_invoice(
        self,
        payload: InvoiceCreate,
        actor_user_id: UUID | None = None,
        actor_role: str | None = None,
    ) -> InvoiceResponse:
        appointment = self._get_appointment_or_404(payload.appointment_id)
        if appointment.status == AppointmentStatus.CANCELLED:
            raise ValueError("Cannot invoice a cancelled appointment")
        if self._get_invoice_by_appointment(payload.appointment_id):
            raise ValueError("An invoice already exists for this appointment")

        subtotal = sum(item.quantity * item.unit_price for item in payload.line_items)
        for item in payload.line_items:
            expected = round(item.quantity * item.unit_price, 2)
            if round(item.amount, 2) != expected:
                raise ValueError(
                    f"Line item '{item.description}': amount {item.amount} does not "
                    f"match quantity × unit_price ({expected})"
                )
        total = max(0.0, round(subtotal - payload.discount_amount, 2))
        invoice = Invoice(
            # Snapshot copied from the appointment; nullable for clinic work.
            hospital_id=appointment.hospital_id,
            appointment_id=appointment.id,
            patient_id=appointment.patient_id,
            invoice_number=self._generate_invoice_number(),
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
        self.db.flush()
        AuditLogService(self.db).record(
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            action="invoice.created",
            target_type="invoice",
            target_id=invoice.id,
            summary=f"Created invoice {invoice.invoice_number}",
            details={
                "appointment_id": str(invoice.appointment_id),
                "patient_id": str(invoice.patient_id),
                "total_amount": float(invoice.total_amount),
            },
        )
        self.db.commit()
        self.db.refresh(invoice)
        return self._to_response(invoice)

    def issue_invoice(
        self,
        invoice_id: UUID,
        actor_user_id: UUID | None = None,
        actor_role: str | None = None,
    ) -> InvoiceResponse:
        invoice = self._get_or_404(invoice_id)
        if invoice.status != InvoiceStatus.DRAFT:
            raise ValueError(f"Invoice is already {invoice.status.value}")
        invoice.status = InvoiceStatus.ISSUED
        invoice.issued_at = datetime.now(UTC)
        AuditLogService(self.db).record(
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            action="invoice.issued",
            target_type="invoice",
            target_id=invoice.id,
            summary=f"Issued invoice {invoice.invoice_number}",
            details={
                "appointment_id": str(invoice.appointment_id),
                "patient_id": str(invoice.patient_id),
                "total_amount": float(invoice.total_amount),
            },
        )
        self.db.commit()
        self.db.refresh(invoice)
        return self._to_response(invoice)

    def record_payment(
        self, invoice_id: UUID, payload: PaymentRequest
    ) -> InvoiceResponse:
        invoice = self._get_or_404(invoice_id)
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

        invoice.amount_paid = round(
            float(invoice.amount_paid) + float(payload.amount_paid), 2
        )
        invoice.balance_due = round(
            float(invoice.total_amount) - float(invoice.amount_paid), 2
        )
        invoice.payment_method = payload.payment_method
        invoice.transaction_reference = payload.transaction_reference
        if invoice.balance_due <= 0:
            invoice.status = InvoiceStatus.PAID
            invoice.paid_at = datetime.now(UTC)
            invoice.balance_due = 0.0
        else:
            invoice.status = InvoiceStatus.PARTIALLY_PAID
        self.db.commit()
        self.db.refresh(invoice)
        return self._to_response(invoice)

    def cancel_invoice(
        self,
        invoice_id: UUID,
        actor_user_id: UUID | None = None,
        actor_role: str | None = None,
    ) -> InvoiceResponse:
        invoice = self._get_or_404(invoice_id)
        if invoice.status == InvoiceStatus.PAID:
            raise ValueError("Cannot cancel a fully paid invoice")
        invoice.status = InvoiceStatus.CANCELLED
        AuditLogService(self.db).record(
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            action="invoice.cancelled",
            target_type="invoice",
            target_id=invoice.id,
            summary=f"Cancelled invoice {invoice.invoice_number}",
            details={
                "appointment_id": str(invoice.appointment_id),
                "patient_id": str(invoice.patient_id),
                "total_amount": float(invoice.total_amount),
            },
        )
        self.db.commit()
        self.db.refresh(invoice)
        return self._to_response(invoice)

    def get_by_id_for_actor(
        self, invoice_id: UUID, actor_user_id: UUID, actor_role: str
    ) -> InvoiceResponse:
        invoice = self._get_or_404(invoice_id)
        if not self._can_view(invoice, actor_user_id, actor_role):
            raise PermissionError("Access denied")
        return self._to_response(invoice)

    def list_for_actor(
        self,
        actor_user_id: UUID,
        actor_role: str,
        params: PaginationParams,
        status: InvoiceStatus | None = None,
    ) -> PaginatedResponse[InvoiceResponse]:
        query = self.db.query(Invoice).filter(Invoice.deleted_at.is_(None))
        if actor_role == UserRole.PATIENT.value:
            query = query.join(Patient, Invoice.patient_id == Patient.id).filter(
                Patient.user_id == actor_user_id,
                Patient.deleted_at.is_(None),
            )
        elif actor_role == UserRole.DOCTOR.value:
            query = (
                query.join(Appointment, Invoice.appointment_id == Appointment.id)
                .join(Doctor, Appointment.doctor_id == Doctor.id)
                .filter(
                    Doctor.user_id == actor_user_id,
                    Doctor.deleted_at.is_(None),
                )
            )
        elif actor_role != UserRole.WEBSITE_ADMIN.value:
            raise PermissionError("Access denied")
        if status:
            query = query.filter(Invoice.status == status)

        total = query.count()
        invoices = (
            query.order_by(Invoice.created_at.desc())
            .offset((params.page - 1) * params.page_size)
            .limit(params.page_size)
            .all()
        )
        return PaginatedResponse(
            data=[self._to_response(invoice) for invoice in invoices],
            total=total,
            page=params.page,
            page_size=params.page_size,
            total_pages=(total + params.page_size - 1) // params.page_size,
        )

    def _can_view(
        self, invoice: Invoice, actor_user_id: UUID, actor_role: str
    ) -> bool:
        if actor_role == UserRole.WEBSITE_ADMIN.value:
            return True
        if actor_role == UserRole.PATIENT.value:
            return (
                self.db.query(Patient.id)
                .filter(
                    Patient.id == invoice.patient_id,
                    Patient.user_id == actor_user_id,
                    Patient.deleted_at.is_(None),
                )
                .first()
                is not None
            )
        if actor_role == UserRole.DOCTOR.value:
            return (
                self.db.query(Appointment.id)
                .join(Doctor, Appointment.doctor_id == Doctor.id)
                .filter(
                    Appointment.id == invoice.appointment_id,
                    Appointment.deleted_at.is_(None),
                    Doctor.user_id == actor_user_id,
                    Doctor.deleted_at.is_(None),
                )
                .first()
                is not None
            )
        return False

    def _generate_invoice_number(self) -> str:
        year = datetime.now(UTC).year
        year_start = datetime(year, 1, 1, tzinfo=UTC)
        count = (
            self.db.query(func.count(Invoice.id))
            .filter(Invoice.created_at >= year_start)
            .scalar()
            or 0
        )
        return f"INV-{year}-{count + 1:05d}"

    def _get_or_404(self, invoice_id: UUID) -> Invoice:
        invoice = (
            self.db.query(Invoice)
            .filter(Invoice.id == invoice_id, Invoice.deleted_at.is_(None))
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

    def _get_appointment_or_404(self, appointment_id: UUID) -> Appointment:
        appointment = (
            self.db.query(Appointment)
            .filter(
                Appointment.id == appointment_id,
                Appointment.deleted_at.is_(None),
            )
            .first()
        )
        if not appointment:
            raise LookupError("Appointment not found")
        return appointment

    @staticmethod
    def _to_response(invoice: Invoice) -> InvoiceResponse:
        from app.schemas.invoice import InvoiceLineItem

        return InvoiceResponse(
            id=invoice.id,
            invoice_number=invoice.invoice_number,
            appointment_id=invoice.appointment_id,
            patient_id=invoice.patient_id,
            status=invoice.status,
            line_items=[
                InvoiceLineItem(**item) for item in (invoice.line_items or [])
            ],
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
