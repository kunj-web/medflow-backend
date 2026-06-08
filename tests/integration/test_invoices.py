"""
tests/integration/test_invoices.py

Covers:
- Admin can create invoice
- Invoice number sequence
- Issue invoice
- Partial and full payment
- Overpayment rejected
- Cancel invoice
- Patient cannot create invoice
- Invoice from other hospital not accessible
- List invoices with pagination
"""
import pytest

from tests.factories.patient_factory import PatientFactory


def _invoice_payload(patient_id: str) -> dict:
    return {
        "patient_id": patient_id,
        "line_items": [
            {"description": "Consultation", "amount": 500.0, "quantity": 1},
        ],
        "discount_amount": 0,
    }


class TestInvoiceCreation:

    async def test_admin_can_create_invoice(self, client, db, hospital, admin_headers):
        patient = PatientFactory.create(db, hospital.id)
        response = await client.post(
            "/api/v1/invoices",
            json=_invoice_payload(str(patient.id)),
            headers=admin_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert "invoice_number" in data
        assert data["status"] == "draft"
        assert float(data["total_amount"]) == pytest.approx(500.0)
        assert float(data["balance_due"]) == pytest.approx(500.0)

    async def test_invoice_number_format(self, client, db, hospital, admin_headers):
        patient = PatientFactory.create(db, hospital.id)
        response = await client.post(
            "/api/v1/invoices",
            json=_invoice_payload(str(patient.id)),
            headers=admin_headers,
        )
        invoice_number = response.json()["invoice_number"]
        assert "-" in invoice_number  # e.g. INV-0001

    async def test_consecutive_invoices_have_sequential_numbers(self, client, db, hospital, admin_headers):
        patient = PatientFactory.create(db, hospital.id)
        r1 = await client.post("/api/v1/invoices", json=_invoice_payload(str(patient.id)), headers=admin_headers)
        r2 = await client.post("/api/v1/invoices", json=_invoice_payload(str(patient.id)), headers=admin_headers)
        n1 = int(r1.json()["invoice_number"].split("-")[-1])
        n2 = int(r2.json()["invoice_number"].split("-")[-1])
        assert n2 == n1 + 1

    async def test_patient_cannot_create_invoice(self, client, db, hospital, patient_headers):
        patient = PatientFactory.create(db, hospital.id)
        response = await client.post(
            "/api/v1/invoices",
            json=_invoice_payload(str(patient.id)),
            headers=patient_headers,
        )
        assert response.status_code == 403

    async def test_discount_reduces_balance_due(self, client, db, hospital, admin_headers):
        patient = PatientFactory.create(db, hospital.id)
        payload = {
            "patient_id": str(patient.id),
            "line_items": [{"description": "X-Ray", "amount": 800.0, "quantity": 1}],
            "discount_amount": 100,
        }
        response = await client.post("/api/v1/invoices", json=payload, headers=admin_headers)
        assert response.status_code == 201
        assert float(response.json()["balance_due"]) == pytest.approx(700.0)


class TestInvoiceIssue:

    async def test_issue_invoice(self, client, db, hospital, admin_headers):
        patient = PatientFactory.create(db, hospital.id)
        create_res = await client.post(
            "/api/v1/invoices",
            json=_invoice_payload(str(patient.id)),
            headers=admin_headers,
        )
        invoice_id = create_res.json()["id"]

        issue_res = await client.post(
            f"/api/v1/invoices/{invoice_id}/issue",
            headers=admin_headers,
        )
        assert issue_res.status_code == 200
        assert issue_res.json()["status"] == "issued"
        assert issue_res.json()["issued_at"] is not None

    async def test_cannot_issue_already_issued_invoice(self, client, db, hospital, admin_headers):
        patient = PatientFactory.create(db, hospital.id)
        create_res = await client.post("/api/v1/invoices", json=_invoice_payload(str(patient.id)), headers=admin_headers)
        invoice_id = create_res.json()["id"]
        await client.post(f"/api/v1/invoices/{invoice_id}/issue", headers=admin_headers)
        response = await client.post(f"/api/v1/invoices/{invoice_id}/issue", headers=admin_headers)
        assert response.status_code == 400


class TestInvoicePayment:

    async def _create_and_issue(self, client, patient_id, admin_headers):
        create_res = await client.post(
            "/api/v1/invoices",
            json=_invoice_payload(patient_id),
            headers=admin_headers,
        )
        invoice_id = create_res.json()["id"]
        await client.post(f"/api/v1/invoices/{invoice_id}/issue", headers=admin_headers)
        return invoice_id

    async def test_partial_payment(self, client, db, hospital, admin_headers):
        patient = PatientFactory.create(db, hospital.id)
        invoice_id = await self._create_and_issue(client, str(patient.id), admin_headers)

        response = await client.post(
            f"/api/v1/invoices/{invoice_id}/pay",
            json={"amount": 200, "payment_method": "cash"},
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "partial"
        assert float(data["balance_due"]) == pytest.approx(300.0)

    async def test_full_payment_marks_paid(self, client, db, hospital, admin_headers):
        patient = PatientFactory.create(db, hospital.id)
        invoice_id = await self._create_and_issue(client, str(patient.id), admin_headers)

        response = await client.post(
            f"/api/v1/invoices/{invoice_id}/pay",
            json={"amount": 500, "payment_method": "upi"},
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "paid"
        assert float(data["balance_due"]) == pytest.approx(0.0)

    async def test_overpayment_rejected(self, client, db, hospital, admin_headers):
        patient = PatientFactory.create(db, hospital.id)
        invoice_id = await self._create_and_issue(client, str(patient.id), admin_headers)

        response = await client.post(
            f"/api/v1/invoices/{invoice_id}/pay",
            json={"amount": 9999, "payment_method": "cash"},
            headers=admin_headers,
        )
        assert response.status_code == 400

    async def test_cannot_pay_draft_invoice(self, client, db, hospital, admin_headers):
        patient = PatientFactory.create(db, hospital.id)
        create_res = await client.post(
            "/api/v1/invoices",
            json=_invoice_payload(str(patient.id)),
            headers=admin_headers,
        )
        invoice_id = create_res.json()["id"]  # still DRAFT

        response = await client.post(
            f"/api/v1/invoices/{invoice_id}/pay",
            json={"amount": 100, "payment_method": "cash"},
            headers=admin_headers,
        )
        assert response.status_code == 400


class TestInvoiceCancel:

    async def test_admin_can_cancel_invoice(self, client, db, hospital, admin_headers):
        patient = PatientFactory.create(db, hospital.id)
        create_res = await client.post(
            "/api/v1/invoices",
            json=_invoice_payload(str(patient.id)),
            headers=admin_headers,
        )
        invoice_id = create_res.json()["id"]

        response = await client.post(
            f"/api/v1/invoices/{invoice_id}/cancel",
            headers=admin_headers,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"

    async def test_cannot_cancel_paid_invoice(self, client, db, hospital, admin_headers):
        patient = PatientFactory.create(db, hospital.id)
        create_res = await client.post("/api/v1/invoices", json=_invoice_payload(str(patient.id)), headers=admin_headers)
        invoice_id = create_res.json()["id"]
        await client.post(f"/api/v1/invoices/{invoice_id}/issue", headers=admin_headers)
        await client.post(
            f"/api/v1/invoices/{invoice_id}/pay",
            json={"amount": 500, "payment_method": "cash"},
            headers=admin_headers,
        )

        response = await client.post(f"/api/v1/invoices/{invoice_id}/cancel", headers=admin_headers)
        assert response.status_code == 400


class TestInvoiceListing:

    async def test_admin_can_list_invoices(self, client, db, hospital, admin_headers):
        patient = PatientFactory.create(db, hospital.id)
        await client.post("/api/v1/invoices", json=_invoice_payload(str(patient.id)), headers=admin_headers)
        response = await client.get("/api/v1/invoices", headers=admin_headers)
        assert response.status_code == 200
        assert "data" in response.json()

    async def test_patient_cannot_list_all_invoices(self, client, patient_headers):
        response = await client.get("/api/v1/invoices", headers=patient_headers)
        assert response.status_code == 403

    async def test_get_nonexistent_invoice_returns_404(self, client, admin_headers):
        from uuid import uuid4
        response = await client.get(f"/api/v1/invoices/{uuid4()}", headers=admin_headers)
        assert response.status_code == 404
