from datetime import date, datetime
from typing import List, Optional, Any
from pydantic import BaseModel, EmailStr, Field, field_validator


class RecipientRawInput(BaseModel):
    name: Optional[str] = ""
    email: Optional[str] = ""


class RecipientSchema(BaseModel):
    name: str = Field(..., description="Recipient's full name")
    email: EmailStr = Field(..., description="Recipient's email address")

    @field_validator("name")

    def name_must_not_be_empty(cls, v: str) -> str:
        stripped = (v or "").strip()
        if not stripped:
            raise ValueError("Recipient name must not be empty or blank")
        return stripped


class JobCreateRequest(BaseModel):
    event_name: str = Field(..., description="Name of the event or course")
    certificate_date: date = Field(..., description="Date on the certificate (YYYY-MM-DD)")
    recipients: List[RecipientRawInput] = Field(..., min_length=1, description="List of recipients")

    @field_validator("event_name")

    def event_name_must_not_be_empty(cls, v: str) -> str:
        stripped = (v or "").strip()
        if not stripped:
            raise ValueError("Event name must not be empty or blank")
        return stripped


class JobCreateResponse(BaseModel):
    job_id: str
    status: str
    total: int


class CertificateSummary(BaseModel):
    certificate_id: str
    recipient_name: str
    recipient_email: Optional[str] = None
    status: str
    error: Optional[str] = None


class JobStatusResponse(BaseModel):
    job_id: str
    event_name: str
    certificate_date: str
    status: str
    total: int
    completed: int
    successful: int
    failed: int
    progress_percentage: float
    certificates: List[CertificateSummary]


class JobListCertificatesResponse(BaseModel):
    job_id: str
    certificates: List[CertificateSummary]
