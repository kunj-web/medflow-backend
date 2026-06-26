from datetime import date, datetime, time, timedelta
from uuid import uuid4

import pytest

from app.core.security import create_token_pair
from app.models.appointment import Appointment
from app.models.enums import (
    AccountStatus,
    AppointmentStatus,
    AppointmentType,
    DayOfWeek,
    UserRole,
)
from tests.factories.doctor_factory import DoctorFactory
from tests.factories.patient_factory import PatientFactory


def next_weekday(day: DayOfWeek) -> date:
    target = list(DayOfWeek).index(day)
    today = date.today()
    days_ahead = (target - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return today + timedelta(days=days_ahead)


def headers_for(user_id, role=UserRole.PATIENT):
    tokens = create_token_pair(
        str(user_id),
        role.value,
        AccountStatus.ACTIVE.value,
        role == UserRole.WEBSITE_ADMIN,
    )
    return {"Authorization": f"Bearer {tokens['access_token']}"}


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


def invoice_payload(appointment_id, amount=500.0, discount=0.0):
    return {
        "appointment_id": str(appointment_id),
        "line_items": [
            {
                "description": "Consultation",
                "quantity": 1,
                "unit_price": amount,
                "amount": amount,
            }
        ],
        "discount_amount": discount,
    }


async def create_invoice(client, appointment_id, admin_headers, amount=500.0):
    return await client.post(
        "/api/v1/invoices",
        json=invoice_payload(appointment_id, amount=amount),
        headers=admin_headers,
    )


class TestInvoiceCreation:
    async def test_admin_can_create_invoice(self, client, db, hospital, admin_headers):
        appointment, patient, _ = create_appointment(db, hospital)

        response = await create_invoice(client, appointment.id, admin_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["patient_id"] == str(patient.id)
        assert data["status"] == "draft"
        assert float(data["total_amount"]) == pytest.approx(500.0)
        assert float(data["balance_due"]) == pytest.approx(500.0)

    async def test_invoice_number_format(self, client, db, hospital, admin_headers):
        appointment, _, _ = create_appointment(db, hospital)

        response = await create_invoice(client, appointment.id, admin_headers)

        assert response.json()["invoice_number"].startswith("INV-")

    async def test_consecutive_invoices_have_sequential_numbers(
        self, client, db, hospital, admin_headers
    ):
        first, _, _ = create_appointment(db, hospital)
        second, _, _ = create_appointment(db, hospital)

        r1 = await create_invoice(client, first.id, admin_headers)
        r2 = await create_invoice(client, second.id, admin_headers)

        n1 = int(r1.json()["invoice_number"].split("-")[-1])
        n2 = int(r2.json()["invoice_number"].split("-")[-1])
        assert n2 == n1 + 1

    async def test_patient_cannot_create_invoice(self, client, db, hospital):
        appointment, patient, _ = create_appointment(db, hospital)

        response = await client.post(
            "/api/v1/invoices",
            json=invoice_payload(appointment.id),
            headers=headers_for(patient.user_id),
        )

        assert response.status_code == 403

    async def test_duplicate_invoice_for_appointment_returns_409(
        self, client, db, hospital, admin_headers
    ):
        appointment, _, _ = create_appointment(db, hospital)
        await create_invoice(client, appointment.id, admin_headers)

        response = await create_invoice(client, appointment.id, admin_headers)

        assert response.status_code == 409

    async def test_discount_reduces_balance_due(self, client, db, hospital, admin_headers):
        appointment, _, _ = create_appointment(db, hospital)

        response = await client.post(
            "/api/v1/invoices",
            json=invoice_payload(appointment.id, amount=800.0, discount=100.0),
            headers=admin_headers,
        )

        assert response.status_code == 201
        assert float(response.json()["balance_due"]) == pytest.approx(700.0)


class TestInvoiceIssue:
    async def test_issue_invoice(self, client, db, hospital, admin_headers):
        appointment, _, _ = create_appointment(db, hospital)
        invoice_id = (await create_invoice(client, appointment.id, admin_headers)).json()[
            "id"
        ]

        response = await client.post(
            f"/api/v1/invoices/{invoice_id}/issue",
            headers=admin_headers,
        )

        assert response.status_code == 200
        assert response.json()["status"] == "issued"
        assert response.json()["issued_at"] is not None

    async def test_cannot_issue_already_issued_invoice(
        self, client, db, hospital, admin_headers
    ):
        appointment, _, _ = create_appointment(db, hospital)
        invoice_id = (await create_invoice(client, appointment.id, admin_headers)).json()[
            "id"
        ]
        await client.post(f"/api/v1/invoices/{invoice_id}/issue", headers=admin_headers)

        response = await client.post(
            f"/api/v1/invoices/{invoice_id}/issue",
            headers=admin_headers,
        )

        assert response.status_code == 409


class TestInvoicePayment:
    async def create_and_issue(self, client, db, hospital, admin_headers):
        appointment, _, _ = create_appointment(db, hospital)
        invoice_id = (await create_invoice(client, appointment.id, admin_headers)).json()[
            "id"
        ]
        await client.post(f"/api/v1/invoices/{invoice_id}/issue", headers=admin_headers)
        return invoice_id

    async def test_partial_payment(self, client, db, hospital, admin_headers):
        invoice_id = await self.create_and_issue(client, db, hospital, admin_headers)

        response = await client.post(
            f"/api/v1/invoices/{invoice_id}/pay",
            json={"amount_paid": 200, "payment_method": "cash"},
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "partially_paid"
        assert float(data["balance_due"]) == pytest.approx(300.0)

    async def test_full_payment_marks_paid(self, client, db, hospital, admin_headers):
        invoice_id = await self.create_and_issue(client, db, hospital, admin_headers)

        response = await client.post(
            f"/api/v1/invoices/{invoice_id}/pay",
            json={"amount_paid": 500, "payment_method": "upi"},
            headers=admin_headers,
        )

        assert response.status_code == 200
        assert response.json()["status"] == "paid"
        assert float(response.json()["balance_due"]) == pytest.approx(0.0)

    async def test_overpayment_rejected(self, client, db, hospital, admin_headers):
        invoice_id = await self.create_and_issue(client, db, hospital, admin_headers)

        response = await client.post(
            f"/api/v1/invoices/{invoice_id}/pay",
            json={"amount_paid": 9999, "payment_method": "cash"},
            headers=admin_headers,
        )

        assert response.status_code == 422

    async def test_cannot_pay_draft_invoice(self, client, db, hospital, admin_headers):
        appointment, _, _ = create_appointment(db, hospital)
        invoice_id = (await create_invoice(client, appointment.id, admin_headers)).json()[
            "id"
        ]

        response = await client.post(
            f"/api/v1/invoices/{invoice_id}/pay",
            json={"amount_paid": 100, "payment_method": "cash"},
            headers=admin_headers,
        )

        assert response.status_code == 422


class TestInvoiceCancel:
    async def test_admin_can_cancel_invoice(self, client, db, hospital, admin_headers):
        appointment, _, _ = create_appointment(db, hospital)
        invoice_id = (await create_invoice(client, appointment.id, admin_headers)).json()[
            "id"
        ]

        response = await client.post(
            f"/api/v1/invoices/{invoice_id}/cancel",
            headers=admin_headers,
        )

        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"

    async def test_cannot_cancel_paid_invoice(self, client, db, hospital, admin_headers):
        invoice_id = await self._create_paid_invoice(client, db, hospital, admin_headers)

        response = await client.post(
            f"/api/v1/invoices/{invoice_id}/cancel",
            headers=admin_headers,
        )

        assert response.status_code == 409

    async def _create_paid_invoice(self, client, db, hospital, admin_headers):
        appointment, _, _ = create_appointment(db, hospital)
        invoice_id = (await create_invoice(client, appointment.id, admin_headers)).json()[
            "id"
        ]
        await client.post(f"/api/v1/invoices/{invoice_id}/issue", headers=admin_headers)
        await client.post(
            f"/api/v1/invoices/{invoice_id}/pay",
            json={"amount_paid": 500, "payment_method": "cash"},
            headers=admin_headers,
        )
        return invoice_id


class TestInvoiceListing:
    async def test_admin_can_list_invoices(self, client, db, hospital, admin_headers):
        appointment, _, _ = create_appointment(db, hospital)
        await create_invoice(client, appointment.id, admin_headers)

        response = await client.get("/api/v1/invoices", headers=admin_headers)

        assert response.status_code == 200
        assert response.json()["total"] == 1

    async def test_patient_lists_only_own_invoices(self, client, db, hospital, admin_headers):
        appointment, patient, _ = create_appointment(db, hospital)
        other_appointment, other_patient, _ = create_appointment(db, hospital)
        await create_invoice(client, appointment.id, admin_headers)
        await create_invoice(client, other_appointment.id, admin_headers)

        response = await client.get(
            "/api/v1/invoices",
            headers=headers_for(patient.user_id),
        )

        assert response.status_code == 200
        assert response.json()["total"] == 1
        assert response.json()["data"][0]["patient_id"] == str(patient.id)
        assert response.json()["data"][0]["patient_id"] != str(other_patient.id)

    async def test_get_nonexistent_invoice_returns_404(self, client, admin_headers):
        response = await client.get(
            f"/api/v1/invoices/{uuid4()}",
            headers=admin_headers,
        )

        assert response.status_code == 404
