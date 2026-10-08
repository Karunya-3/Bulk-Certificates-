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


def test_individual_failure_isolation(client):
    db = get_db()
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Manually insert job document into db (to avoid TestClient automatically processing with real generator)
    job_doc = {
        "event_name": "Resilience Training",
        "certificate_date": "2026-10-08",
        "status": "PENDING",
        "total_count": 3,
        "success_count": 0,
        "failure_count": 0,
        "created_at": now_iso,
        "started_at": None,
        "completed_at": None,
    }
    insert_res = db.jobs.insert_one(job_doc)
    job_id_str = str(insert_res.inserted_id)

    # 2. Insert certificates
    recipients = [
        {"name": "Recipient A", "email": "a@example.com"},
        {"name": "Recipient B", "email": "b@example.com"},
        {"name": "Recipient C", "email": "c@example.com"},
    ]

    for idx, r in enumerate(recipients):
        db.certificates.insert_one({
            "job_id": job_id_str,
            "certificate_id": f"CERT-FAIL-{idx}",
            "recipient_name": r["name"],
            "recipient_email": r["email"],
            "status": "PENDING",
            "file_path": None,
            "error_message": None,
            "created_at": now_iso,
            "completed_at": None,
        })

    # 3. Process job with Mock Generator where Recipient B fails
    mock_generator = MockCertificateGeneratorWithFailure(failing_recipient_name="Recipient B")
    process_bulk_job(job_id_str, generator=mock_generator)

    # 4. Check job status via API
    res_status = client.get(f"/api/v1/certificates/jobs/{job_id_str}")
    assert res_status.status_code == 200
    data = res_status.json()

    assert data["status"] == "COMPLETED_WITH_ERRORS"
    assert data["total"] == 3
    assert data["completed"] == 3
    assert data["successful"] == 2
    assert data["failed"] == 1
    assert data["progress_percentage"] == 100.0

    # Verify Recipient C was still processed despite Recipient B failing!
    certs_map = {c["recipient_name"]: c for c in data["certificates"]}
    assert certs_map["Recipient A"]["status"] == "COMPLETED"
    assert certs_map["Recipient B"]["status"] == "FAILED"
    assert "Simulated generation error" in certs_map["Recipient B"]["error"]
    assert certs_map["Recipient C"]["status"] == "COMPLETED"
