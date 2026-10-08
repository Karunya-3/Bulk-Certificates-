def test_job_status_progress_tracking(client):
    payload = {
        "event_name": "FastAPI Masterclass",
        "certificate_date": "2026-10-08",
        "recipients": [
            {"name": "Alice Smith", "email": "alice@example.com"},
            {"name": "Bob Johnson", "email": "bob@example.com"},
        ],
    }

    response = client.post("/api/v1/certificates/jobs", json=payload)
    assert response.status_code == 202
    job_id = response.json()["job_id"]

    # FastAPI TestClient executes BackgroundTasks automatically, so the job completes
    res_completed = client.get(f"/api/v1/certificates/jobs/{job_id}")
    assert res_completed.status_code == 200
    comp_data = res_completed.json()

    assert comp_data["job_id"] == job_id
    assert comp_data["status"] == "COMPLETED"
    assert comp_data["total"] == 2
    assert comp_data["completed"] == 2
    assert comp_data["successful"] == 2
    assert comp_data["failed"] == 0
    assert comp_data["progress_percentage"] == 100.0
    assert len(comp_data["certificates"]) == 2


def test_job_certificates_listing_endpoint(client):
    payload = {
        "event_name": "Docker Essentials",
        "certificate_date": "2026-10-08",
        "recipients": [
            {"name": "Charlie Brown", "email": "charlie@example.com"}
        ],
    }

    res_create = client.post("/api/v1/certificates/jobs", json=payload)
    job_id = res_create.json()["job_id"]

    res_list = client.get(f"/api/v1/certificates/jobs/{job_id}/certificates")
    assert res_list.status_code == 200
    data = res_list.json()
    assert data["job_id"] == job_id
    assert len(data["certificates"]) == 1
    assert data["certificates"][0]["recipient_name"] == "Charlie Brown"
