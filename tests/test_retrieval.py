from datetime import datetime, timezone
from app.db.mongodb import get_db
from app.services.job_processor import process_bulk_job


class MockCertificateGeneratorWithFailure:
    def __init__(self, failing_recipient_name: str):
        self.failing_recipient_name = failing_recipient_name

    def generate(self, recipient_name: str, event_name: str, certificate_date, certificate_id: str) -> str:
        if recipient_name == self.failing_recipient_name:
            raise RuntimeError(f"Simulated generation error for {recipient_name}")
        return f"generated_certificates/{certificate_id}.pdf"


def test_certificate_retrieval_success(client):
    payload = {
        "event_name": "API Design",
        "certificate_date": "2026-10-08",
        "recipients": [{"name": "John Doe", "email": "john@example.com"}],
    }

    res_create = client.post("/api/v1/certificates/jobs", json=payload)
    job_id = res_create.json()["job_id"]

    # Get certificate ID (TestClient already processed background task)
    res_job = client.get(f"/api/v1/certificates/jobs/{job_id}")
    cert_id = res_job.json()["certificates"][0]["certificate_id"]

    # Download PDF
    res_cert = client.get(f"/api/v1/certificates/{cert_id}")
    assert res_cert.status_code == 200
    assert res_cert.headers["content-type"] == "application/pdf"
    assert res_cert.content.startswith(b"%PDF-")


def test_certificate_retrieval_nonexistent(client):
    res_cert = client.get("/api/v1/certificates/CERT-NONEXISTENT")
    assert res_cert.status_code == 404
    data = res_cert.json()
    assert data["error"]["code"] == "CERTIFICATE_NOT_FOUND"


def test_certificate_retrieval_still_processing(client):
    db = get_db()
    now_iso = datetime.now(timezone.utc).isoformat()
    cert_id = "CERT-PROCESSING-001"

    # Manually insert a certificate with PENDING status
    db.certificates.insert_one({
        "job_id": "job_123",
        "certificate_id": cert_id,
        "recipient_name": "Alice Smith",
        "recipient_email": "alice@example.com",
        "status": "PROCESSING",
        "file_path": None,
        "error_message": None,
        "created_at": now_iso,
        "completed_at": None,
    })

    # Retrieve certificate while in PROCESSING state
    res_cert = client.get(f"/api/v1/certificates/{cert_id}")
    assert res_cert.status_code == 409
    data = res_cert.json()
    assert data["error"]["code"] == "CERTIFICATE_STILL_PROCESSING"


def test_certificate_retrieval_failed(client):
    db = get_db()
    now_iso = datetime.now(timezone.utc).isoformat()
    cert_id = "CERT-FAILED-001"

    # Manually insert a certificate with FAILED status
    db.certificates.insert_one({
        "job_id": "job_123",
        "certificate_id": cert_id,
        "recipient_name": "Failed User",
        "recipient_email": "fail@example.com",
        "status": "FAILED",
        "file_path": None,
        "error_message": "ReportLab rendering crashed",
        "created_at": now_iso,
        "completed_at": now_iso,
    })

    res_cert = client.get(f"/api/v1/certificates/{cert_id}")
    assert res_cert.status_code == 409
    data = res_cert.json()
    assert data["error"]["code"] == "CERTIFICATE_GENERATION_FAILED"
    assert "ReportLab rendering crashed" in data["error"]["message"]
