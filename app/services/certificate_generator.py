import os
from datetime import date, datetime
from typing import Union
from pathlib import Path

from app.core.config import settings
from templates.certificate_template import build_certificate_pdf


class CertificateGenerator:
    """
    Service responsible for generating certificate PDF documents.
    """

    def __init__(self, output_dir: Union[str, Path] = None):
        self.output_dir = Path(output_dir) if output_dir else settings.certs_output_dir

    def generate(
        self,
        recipient_name: str,
        event_name: str,
        certificate_date: Union[date, str, datetime],
        certificate_id: str,
    ) -> str:
        """
        Generates a PDF certificate for a recipient and returns the relative file path.
        """
        # Format date string nicely if date/datetime object is provided
        if isinstance(certificate_date, (date, datetime)):
            formatted_date = certificate_date.strftime("%B %d, %Y")
        else:
            formatted_date = str(certificate_date)

        file_name = f"{certificate_id}.pdf"
        full_output_path = self.output_dir / file_name

        # Call template builder to generate PDF
        build_certificate_pdf(
            output_path=str(full_output_path),
            recipient_name=recipient_name,
            event_name=event_name,
            certificate_date=formatted_date,
            certificate_id=certificate_id,
        )

        # Store relative file path for database consistency
        relative_path = f"generated_certificates/{file_name}"
        return relative_path


# Singleton service instance
certificate_generator_service = CertificateGenerator()
