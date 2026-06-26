from datetime import date, datetime, time, timedelta

import pytest

from app.models.appointment import Appointment
from app.models.enums import (
    AppointmentStatus,
    AppointmentType,
    DayOfWeek,
    InvoiceStatus,
    UserRole,
)
from app.schemas.invoice import InvoiceCreate, InvoiceLineItem, PaymentRequest
from app.schemas.pagination import PaginationParams
from app.services.billing_service import BillingService
from tests.factories.doctor_factory import DoctorFactory
from tests.factories.patient_factory import PatientFactory


def next_weekday(day: DayOfWeek) -> date:
    target = list(DayOfWeek).index(day)
    today = date.today()
    days_ahead = (target - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return today + timedelta(days=days_ahead)


def create_appointment(db, hospital):
    doctor = DoctorFactory.create(db, hospital.id)
    patient = PatientFactory.create(db, hospital.id)
    slot_time = datetime.combine(next_weekday(DayOfWeek.MONDAY), time(10, 0))
    appointment = Appointment(
        hospital_id=hospital.id,
        patient_id=patient.id,
        doctor_id=doctor.id,
        slot_time=slot_time,
        end_time=slot_time + timedelta(minutes=15),
        status=AppointmentStatus.SCHEDULED,
        type=AppointmentType.CONSULTATION,
        token_number=1,
    )
    db.add(appointment)
    db.flush()
    return appointment, patient, doctor


def payload_for(appointment_id, items=None, discount=0.0):
    return InvoiceCreate(
        appointment_id=appointment_id,
        line_items=items
        or [
            InvoiceLineItem(
                description="Consultation",
                quantity=1,
                unit_price=500,
                amount=500,
            )
        ],
        discount_amount=discount,
    )


def create_invoice(db, hospital, items=None, discount=0.0):
    appointment, patient, doctor = create_appointment(db, hospital)
    invoice = BillingService(db).create_invoice(
        payload_for(appointment.id, items=items, discount=discount)
    )
    return invoice, appointment, patient, doctor


class TestInvoiceNumberSequence:
    def test_first_invoice_is_0001(self, db, hospital):
        invoice, _, _, _ = create_invoice(db, hospital)

        assert invoice.invoice_number.endswith("00001")

    def test_second_invoice_increments(self, db, hospital):
        first, _, _, _ = create_invoice(db, hospital)
        second, _, _, _ = create_invoice(db, hospital)

        n1 = int(first.invoice_number.split("-")[-1])
        n2 = int(second.invoice_number.split("-")[-1])
        assert n2 == n1 + 1


class TestInvoiceCreation:
    def test_total_amount_computed_from_line_items(self, db, hospital):
        invoice, _, _, _ = create_invoice(
            db,
            hospital,
            items=[
                InvoiceLineItem(
                    description="Consultation",
                    quantity=1,
                    unit_price=500,
                    amount=500,
                ),
                InvoiceLineItem(
                    description="Lab Test",
                    quantity=2,
                    unit_price=200,
                    amount=400,
                ),
            ],
        )

        assert float(invoice.total_amount) == pytest.approx(900.0)
        assert float(invoice.balance_due) == pytest.approx(900.0)

    def test_discount_reduces_balance_due(self, db, hospital):
        invoice, _, _, _ = create_invoice(db, hospital, discount=100)

        assert float(invoice.balance_due) == pytest.approx(400.0)

    def test_new_invoice_is_draft(self, db, hospital):
        invoice, _, _, _ = create_invoice(db, hospital)

        assert invoice.status == InvoiceStatus.DRAFT

    def test_line_item_amount_must_match_quantity_times_price(self, db, hospital):
        appointment, _, _ = create_appointment(db, hospital)

        with pytest.raises(ValueError, match="does not match"):
            BillingService(db).create_invoice(
                payload_for(
                    appointment.id,
                    items=[
                        InvoiceLineItem(
                            description="Bad",
                            quantity=2,
                            unit_price=200,
                            amount=200,
                        )
                    ],
                )
            )

    def test_cancelled_appointment_cannot_be_invoiced(self, db, hospital):
        appointment, _, _ = create_appointment(db, hospital)
        appointment.status = AppointmentStatus.CANCELLED
        db.flush()

        with pytest.raises(ValueError, match="cancelled appointment"):
            BillingService(db).create_invoice(payload_for(appointment.id))


class TestInvoiceIssue:
    def test_issue_moves_status_to_issued(self, db, hospital):
        invoice, _, _, _ = create_invoice(db, hospital)

        issued = BillingService(db).issue_invoice(invoice.id)

        assert issued.status == InvoiceStatus.ISSUED
        assert issued.issued_at is not None

    def test_cannot_issue_already_issued_invoice(self, db, hospital):
        invoice, _, _, _ = create_invoice(db, hospital)
        service = BillingService(db)
        service.issue_invoice(invoice.id)

        with pytest.raises(ValueError, match="already issued"):
            service.issue_invoice(invoice.id)


class TestPayment:
    def test_partial_payment_reduces_balance(self, db, hospital):
        invoice, _, _, _ = create_invoice(db, hospital)
        service = BillingService(db)
        service.issue_invoice(invoice.id)

        updated = service.record_payment(
            invoice.id,
            PaymentRequest(amount_paid=200, payment_method="cash"),
        )

        assert float(updated.balance_due) == pytest.approx(300.0)
        assert updated.status == InvoiceStatus.PARTIALLY_PAID

    def test_full_payment_marks_paid(self, db, hospital):
        invoice, _, _, _ = create_invoice(db, hospital)
        service = BillingService(db)
        service.issue_invoice(invoice.id)

        paid = service.record_payment(
            invoice.id,
            PaymentRequest(amount_paid=500, payment_method="upi"),
        )

        assert float(paid.balance_due) == pytest.approx(0.0)
        assert paid.status == InvoiceStatus.PAID

    def test_two_partial_payments_sum_correctly(self, db, hospital):
        invoice, _, _, _ = create_invoice(db, hospital)
        service = BillingService(db)
        service.issue_invoice(invoice.id)
        service.record_payment(
            invoice.id,
            PaymentRequest(amount_paid=200, payment_method="cash"),
        )

        final = service.record_payment(
            invoice.id,
            PaymentRequest(amount_paid=300, payment_method="card"),
        )

        assert float(final.balance_due) == pytest.approx(0.0)
        assert final.status == InvoiceStatus.PAID

    def test_overpayment_rejected(self, db, hospital):
        invoice, _, _, _ = create_invoice(db, hospital)
        service = BillingService(db)
        service.issue_invoice(invoice.id)

        with pytest.raises(ValueError, match="exceeds balance due"):
            service.record_payment(
                invoice.id,
                PaymentRequest(amount_paid=9999, payment_method="cash"),
            )

    def test_cannot_pay_draft_invoice(self, db, hospital):
        invoice, _, _, _ = create_invoice(db, hospital)

        with pytest.raises(ValueError, match="draft invoice"):
            BillingService(db).record_payment(
                invoice.id,
                PaymentRequest(amount_paid=100, payment_method="cash"),
            )

    def test_cannot_pay_cancelled_invoice(self, db, hospital):
        invoice, _, _, _ = create_invoice(db, hospital)
        service = BillingService(db)
        service.issue_invoice(invoice.id)
        service.cancel_invoice(invoice.id)

        with pytest.raises(ValueError, match="cancelled invoice"):
            service.record_payment(
                invoice.id,
                PaymentRequest(amount_paid=100, payment_method="cash"),
            )


class TestInvoiceAccess:
    def test_patient_can_view_own_invoice(self, db, hospital):
        invoice, _, patient, _ = create_invoice(db, hospital)

        result = BillingService(db).get_by_id_for_actor(
            invoice.id,
            patient.user_id,
            UserRole.PATIENT.value,
        )

        assert result.id == invoice.id

    def test_other_patient_cannot_view_invoice(self, db, hospital):
        invoice, _, _, _ = create_invoice(db, hospital)
        other_patient = PatientFactory.create(db, hospital.id)

        with pytest.raises(PermissionError, match="Access denied"):
            BillingService(db).get_by_id_for_actor(
                invoice.id,
                other_patient.user_id,
                UserRole.PATIENT.value,
            )

    def test_doctor_can_list_own_invoices(self, db, hospital):
        invoice, _, _, doctor = create_invoice(db, hospital)

        result = BillingService(db).list_for_actor(
            doctor.user_id,
            UserRole.DOCTOR.value,
            PaginationParams(page=1, page_size=20),
        )

        assert result.total == 1
        assert result.data[0].id == invoice.id
