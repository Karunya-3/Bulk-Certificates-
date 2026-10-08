import io
import openpyxl


def test_csv_upload_success(client):
    csv_content = b"Name,Email\nJohn Doe,john@example.com\nAlice Smith,alice@example.com\n"
    files = {"file": ("recipients.csv", csv_content, "text/csv")}
    data = {
        "event_name": "CSV Workshop",
        "certificate_date": "2026-10-08",
    }

    response = client.post("/api/v1/certificates/jobs/upload", data=data, files=files)
    assert response.status_code == 202
    res_data = response.json()
    assert "job_id" in res_data
    assert res_data["total"] == 2

    job_id = res_data["job_id"]
    res_status = client.get(f"/api/v1/certificates/jobs/{job_id}")
    assert res_status.status_code == 200
    assert res_status.json()["status"] == "COMPLETED"


def test_excel_upload_success(client):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Full Name", "Email Address"])
    ws.append(["Bob Johnson", "bob@example.com"])
    ws.append(["Charlie Brown", "charlie@example.com"])

    excel_buffer = io.BytesIO()
    wb.save(excel_buffer)
    excel_buffer.seek(0)

    files = {
        "file": (
            "recipients.xlsx",
            excel_buffer.read(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    data = {
        "event_name": "Excel Masterclass",
        "certificate_date": "2026-10-08",
    }

    response = client.post("/api/v1/certificates/jobs/upload", data=data, files=files)
    assert response.status_code == 202
    res_data = response.json()
    assert res_data["total"] == 2

    job_id = res_data["job_id"]
    res_status = client.get(f"/api/v1/certificates/jobs/{job_id}")
    assert res_status.status_code == 200
    assert res_status.json()["status"] == "COMPLETED"


def test_upload_invalid_file_extension(client):
    files = {"file": ("test.pdf", b"%PDF-dummy", "application/pdf")}
    data = {
        "event_name": "PDF Event",
        "certificate_date": "2026-10-08",
    }
    response = client.post("/api/v1/certificates/jobs/upload", data=data, files=files)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_upload_invalid_row_email(client):
    csv_content = b"Name,Email\nValid User,valid@example.com\nBad User,not-an-email\n"
    files = {"file": ("recipients.csv", csv_content, "text/csv")}
    data = {
        "event_name": "Bad Email Event",
        "certificate_date": "2026-10-08",
    }
    response = client.post("/api/v1/certificates/jobs/upload", data=data, files=files)
    assert response.status_code == 202
    job_id = response.json()["job_id"]

    res_status = client.get(f"/api/v1/certificates/jobs/{job_id}")
    assert res_status.status_code == 200
    data_status = res_status.json()

    assert data_status["status"] == "COMPLETED_WITH_ERRORS"
    assert data_status["total"] == 2
    assert data_status["successful"] == 1
    assert data_status["failed"] == 1

