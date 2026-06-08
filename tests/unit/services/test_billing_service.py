"""
tests/unit/services/test_billing_service.py

Covers:
- Invoice number sequence (INV-0001, INV-0002 …)
- Invoice creation with line items
- Partial payment reduces balance_due
- Full payment sets status to PAID
- Overpayment rejected
- Cannot pay a CANCELLED invoice
- Cannot issue a non-DRAFT invoice
- Hospital scoping — invoice from other hospital not accessible
"""

import pytest

from app.models.enums import InvoiceStatus
from app.schemas.invoice import InvoiceCreate, PaymentCreate
from app.services.billing_service import BillingService
from tests.factories.patient_factory import PatientFactory


def _make_invoice(db, hospital, patient=None, line_items=None):
    """Helper — create a DRAFT invoice via BillingService."""
    if patient is None:
        patient = PatientFactory.create(db, hospital.id)
    if line_items is None:
        line_items = [{"description": "Consultation", "amount": 500.00, "quantity": 1}]
    service = BillingService(db)
    return service.create(
        data=InvoiceCreate(
            patient_id=patient.id,
            line_items=line_items,
            discount_amount=0,
        ),
        hospital_id=hospital.id,
    )


class TestInvoiceNumberSequence:

    def test_first_invoice_is_0001(self, db, hospital):
        invoice = _make_invoice(db, hospital)
        assert invoice.invoice_number.endswith("0001")

    def test_second_invoice_increments(self, db, hospital):
        inv1 = _make_invoice(db, hospital)
        inv2 = _make_invoice(db, hospital)
        # Extract numeric suffixes
        n1 = int(inv1.invoice_number.split("-")[-1])
        n2 = int(inv2.invoice_number.split("-")[-1])
        assert n2 == n1 + 1

    def test_invoice_numbers_unique_across_patients(self, db, hospital):
        p1 = PatientFactory.create(db, hospital.id)
        p2 = PatientFactory.create(db, hospital.id)
        inv1 = _make_invoice(db, hospital, patient=p1)
        inv2 = _make_invoice(db, hospital, patient=p2)
        assert inv1.invoice_number != inv2.invoice_number


class TestInvoiceCreation:

    def test_total_amount_computed_from_line_items(self, db, hospital):
        invoice = _make_invoice(
            db, hospital,
            line_items=[
                {"description": "Consultation", "amount": 500.00, "quantity": 1},
                {"description": "Lab Test", "amount": 200.00, "quantity": 2},
            ],
        )
        # 500 + 200*2 = 900
        assert float(invoice.total_amount) == pytest.approx(900.0)

    def test_discount_reduces_balance_due(self, db, hospital):
        patient = PatientFactory.create(db, hospital.id)
        service = BillingService(db)
        invoice = service.create(
            data=InvoiceCreate(
                patient_id=patient.id,
                line_items=[{"description": "Consultation", "amount": 1000.00, "quantity": 1}],
                discount_amount=100,
            ),
            hospital_id=hospital.id,
        )
        assert float(invoice.balance_due) == pytest.approx(900.0)

    def test_new_invoice_is_draft(self, db, hospital):
        invoice = _make_invoice(db, hospital)
        assert invoice.status == InvoiceStatus.DRAFT

    def test_balance_due_equals_total_minus_discount_on_creation(self, db, hospital):
        patient = PatientFactory.create(db, hospital.id)
        service = BillingService(db)
        invoice = service.create(
            data=InvoiceCreate(
                patient_id=patient.id,
                line_items=[{"description": "X-Ray", "amount": 800.00, "quantity": 1}],
                discount_amount=50,
            ),
            hospital_id=hospital.id,
        )
        assert float(invoice.balance_due) == pytest.approx(750.0)
        assert float(invoice.total_amount) == pytest.approx(800.0)


class TestInvoiceIssue:

    def test_issue_moves_status_to_issued(self, db, hospital):
        invoice = _make_invoice(db, hospital)
        service = BillingService(db)
        issued = service.issue(invoice_id=invoice.id, hospital_id=hospital.id)
        assert issued.status == InvoiceStatus.ISSUED
        assert issued.issued_at is not None

    def test_cannot_issue_already_issued_invoice(self, db, hospital):
        invoice = _make_invoice(db, hospital)
        service = BillingService(db)
        service.issue(invoice_id=invoice.id, hospital_id=hospital.id)
        with pytest.raises(ValueError, match="[Ii]ssue|[Ss]tatus"):
            service.issue(invoice_id=invoice.id, hospital_id=hospital.id)


class TestPartialPayment:

    def test_partial_payment_reduces_balance(self, db, hospital):
        invoice = _make_invoice(db, hospital)  # total = 500, balance = 500
        service = BillingService(db)
        service.issue(invoice_id=invoice.id, hospital_id=hospital.id)

        updated = service.pay(
            invoice_id=invoice.id,
            hospital_id=hospital.id,
            data=PaymentCreate(amount=200, payment_method="cash"),
        )
        assert float(updated.balance_due) == pytest.approx(300.0)
        assert updated.status == InvoiceStatus.PARTIAL

    def test_full_payment_marks_paid(self, db, hospital):
        invoice = _make_invoice(db, hospital)
        service = BillingService(db)
        service.issue(invoice_id=invoice.id, hospital_id=hospital.id)

        paid = service.pay(
            invoice_id=invoice.id,
            hospital_id=hospital.id,
            data=PaymentCreate(amount=500, payment_method="upi"),
        )
        assert float(paid.balance_due) == pytest.approx(0.0)
        assert paid.status == InvoiceStatus.PAID

    def test_two_partial_payments_sum_correctly(self, db, hospital):
        invoice = _make_invoice(db, hospital)
        service = BillingService(db)
        service.issue(invoice_id=invoice.id, hospital_id=hospital.id)

        service.pay(
            invoice_id=invoice.id,
            hospital_id=hospital.id,
            data=PaymentCreate(amount=200, payment_method="cash"),
        )
        final = service.pay(
            invoice_id=invoice.id,
            hospital_id=hospital.id,
            data=PaymentCreate(amount=300, payment_method="card"),
        )
        assert float(final.balance_due) == pytest.approx(0.0)
        assert final.status == InvoiceStatus.PAID

    def test_overpayment_rejected(self, db, hospital):
        invoice = _make_invoice(db, hospital)
        service = BillingService(db)
        service.issue(invoice_id=invoice.id, hospital_id=hospital.id)

        with pytest.raises(ValueError, match="[Oo]verpay|exceed|greater"):
            service.pay(
                invoice_id=invoice.id,
                hospital_id=hospital.id,
                data=PaymentCreate(amount=9999, payment_method="cash"),
            )

    def test_cannot_pay_draft_invoice(self, db, hospital):
        invoice = _make_invoice(db, hospital)  # still DRAFT
        service = BillingService(db)
        with pytest.raises(ValueError, match="[Dd]raft|[Ii]ssue|[Ss]tatus"):
            service.pay(
                invoice_id=invoice.id,
                hospital_id=hospital.id,
                data=PaymentCreate(amount=100, payment_method="cash"),
            )

    def test_cannot_pay_cancelled_invoice(self, db, hospital):
        invoice = _make_invoice(db, hospital)
        service = BillingService(db)
        service.issue(invoice_id=invoice.id, hospital_id=hospital.id)
        service.cancel(invoice_id=invoice.id, hospital_id=hospital.id)

        with pytest.raises(ValueError, match="[Cc]ancel|[Ss]tatus"):
            service.pay(
                invoice_id=invoice.id,
                hospital_id=hospital.id,
                data=PaymentCreate(amount=100, payment_method="cash"),
            )


class TestInvoiceHospitalScoping:

    def test_invoice_from_other_hospital_not_accessible(self, db, hospital):
        from app.models.hospital import Hospital
        other = Hospital(name="Other", primary_color="#000000", currency="INR", timezone="Asia/Kolkata")
        db.add(other)
        db.flush()

        patient = PatientFactory.create(db, other.id)
        other_invoice = _make_invoice(db, other, patient=patient)
        service = BillingService(db)

        with pytest.raises((ValueError, AttributeError)):
            service.issue(invoice_id=other_invoice.id, hospital_id=hospital.id)
