def test_validation_missing_event_name(client):
    payload = {
        "certificate_date": "2026-10-08",
        "recipients": [{"name": "John Doe", "email": "john@example.com"}],
    }
    response = client.post("/api/v1/certificates/jobs", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"


def test_validation_empty_event_name(client):
    payload = {
        "event_name": "   ",
        "certificate_date": "2026-10-08",
        "recipients": [{"name": "John Doe", "email": "john@example.com"}],
    }
    response = client.post("/api/v1/certificates/jobs", json=payload)
    assert response.status_code == 422


def test_validation_invalid_date(client):
    payload = {
        "event_name": "Python Workshop",
        "certificate_date": "not-a-date",
        "recipients": [{"name": "John Doe", "email": "john@example.com"}],
    }
    response = client.post("/api/v1/certificates/jobs", json=payload)
    assert response.status_code == 422


def test_validation_empty_recipient_list(client):
    payload = {
        "event_name": "Python Workshop",
        "certificate_date": "2026-10-08",
        "recipients": [],
    }
    response = client.post("/api/v1/certificates/jobs", json=payload)
    assert response.status_code == 422


def test_validation_invalid_recipient_email_continues_batch(client):
    """
    Verifies that when one recipient has an invalid email, the request is NOT rejected.
    The job is accepted (HTTP 202), valid recipients are processed, and invalid recipient is marked FAILED.
    """
    payload = {
        "event_name": "Resilient Validation Event",
        "certificate_date": "2026-10-08",
        "recipients": [
            {"name": "Valid Recipient", "email": "valid@example.com"},
            {"name": "Invalid Recipient", "email": "not-an-email-no-at-sign"},
        ],
    }
    response = client.post("/api/v1/certificates/jobs", json=payload)
    assert response.status_code == 202
    job_id = response.json()["job_id"]

    res_status = client.get(f"/api/v1/certificates/jobs/{job_id}")
    assert res_status.status_code == 200
    data = res_status.json()

    assert data["status"] == "COMPLETED_WITH_ERRORS"
    assert data["total"] == 2
    assert data["successful"] == 1
    assert data["failed"] == 1

    certs = {c["recipient_name"]: c for c in data["certificates"]}
    assert certs["Valid Recipient"]["status"] == "COMPLETED"
    assert certs["Invalid Recipient"]["status"] == "FAILED"
    assert "Invalid email" in certs["Invalid Recipient"]["error"]

