from bson import ObjectId
from app.db.mongodb import get_db


def test_create_generation_job_success(client):
    payload = {
        "event_name": "Python Workshop",
        "certificate_date": "2026-10-08",
        "recipients": [
            {"name": "John Doe", "email": "john@example.com"},
            {"name": "Alice Smith", "email": "alice@example.com"},
        ],
    }

    response = client.post("/api/v1/certificates/jobs", json=payload)
    assert response.status_code == 202

    data = response.json()
    assert "job_id" in data
    assert data["status"] == "PENDING"
    assert data["total"] == 2

    job_id = data["job_id"]
    db = get_db()

    # Verify MongoDB job document creation
    job_doc = db.jobs.find_one({"_id": ObjectId(job_id)})
    assert job_doc is not None
    assert job_doc["event_name"] == "Python Workshop"
    assert job_doc["total_count"] == 2

    # Verify MongoDB certificate documents creation
    cert_docs = list(db.certificates.find({"job_id": job_id}))
    assert len(cert_docs) == 2
    recipients_in_db = [c["recipient_name"] for c in cert_docs]
    assert "John Doe" in recipients_in_db
    assert "Alice Smith" in recipients_in_db
