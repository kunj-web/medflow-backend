import sqlalchemy as sa
from sqlalchemy import Column, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.base import BaseModel, HospitalScopedMixin
from app.models.enums import InvoiceStatus


class Invoice(BaseModel, HospitalScopedMixin):
    __tablename__ = "invoices"
    __table_args__ = (
        Index("ix_invoice_appointment", "appointment_id"),
        Index("ix_invoice_hospital_status", "hospital_id", "status"),
    )
    appointment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("appointments.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    patient_id = Column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="RESTRICT"),
        nullable=False,
    )
    invoice_number = Column(String(50), nullable=False, unique=True)
    line_items = Column(JSONB, nullable=False, default=list)
    subtotal = Column(Numeric(10, 2), nullable=False, default=0)
    discount_amount = Column(Numeric(10, 2), default=0)
    total_amount = Column(Numeric(10, 2), nullable=False, default=0)
    amount_paid = Column(Numeric(10, 2), default=0)
    balance_due = Column(Numeric(10, 2), default=0)
    status = Column(
        sa.Enum(InvoiceStatus),
        nullable=False,
        default=InvoiceStatus.DRAFT,
    )
    payment_method = Column(String(50), nullable=True)
    transaction_reference = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    issued_at = Column(DateTime(timezone=True), nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    appointment = relationship("Appointment", back_populates="invoice", lazy="raise")
