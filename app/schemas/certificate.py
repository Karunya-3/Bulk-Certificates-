from typing import Optional
from pydantic import BaseModel, Field


class CertificateDetailResponse(BaseModel):
    certificate_id: str
    job_id: str
    recipient_name: str
    recipient_email: str
    status: str
    file_path: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None
