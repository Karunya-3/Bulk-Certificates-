import os
from pathlib import Path
from app.services.certificate_generator import CertificateGenerator


def test_pdf_certificate_generation(tmp_path):
    generator = CertificateGenerator(output_dir=tmp_path)
    cert_id = "CERT-7F92A1C4"

    file_path = generator.generate(
        recipient_name="John Doe",
        event_name="Python Workshop",
        certificate_date="2026-10-08",
        certificate_id=cert_id,
    )

    assert file_path == f"generated_certificates/{cert_id}.pdf"

    expected_full_path = tmp_path / f"{cert_id}.pdf"
    assert expected_full_path.exists()
    assert expected_full_path.stat().st_size > 0

    # Verify header signature of valid PDF
    with open(expected_full_path, "rb") as f:
        header = f.read(5)
        assert header == b"%PDF-"
