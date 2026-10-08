import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from bson import ObjectId
from pydantic import ValidationError
from fastapi import APIRouter, BackgroundTasks, HTTPException, status, File, Form, UploadFile
from fastapi.responses import FileResponse

from app.core.config import settings
from app.db.mongodb import get_db
from app.schemas.job import (
    JobCreateRequest,
    JobCreateResponse,
    JobStatusResponse,
    JobListCertificatesResponse,
    CertificateSummary,
    RecipientSchema,
)
from app.schemas.certificate import CertificateDetailResponse
from app.services.job_processor import process_bulk_job
from app.services.file_parser import parse_recipients_from_file

router = APIRouter(prefix="/api/v1/certificates", tags=["Certificates"])


def generate_unique_cert_id() -> str:
    return f"CERT-{uuid.uuid4().hex[:8].upper()}"


@router.post(
    "/jobs",
    response_model=JobCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create Bulk Certificate Generation Job",
    description="Accepts a bulk certificate request, validates recipients individually (isolating invalid emails/names), creates job and certificate records, and starts background processing.",
)
def create_job(request: JobCreateRequest, background_tasks: BackgroundTasks):
    db = get_db()
    now_iso = datetime.now(timezone.utc).isoformat()
    cert_date_str = request.certificate_date.isoformat()

    if not request.recipients:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Recipient list must contain at least one recipient",
                }
            },
        )

    cert_docs = []
    initial_failure_count = 0
    pending_count = 0

    for idx, r_raw in enumerate(request.recipients, start=1):
        cert_id = generate_unique_cert_id()
        raw_name = (r_raw.name or "").strip()
        raw_email = (r_raw.email or "").strip()

        try:
            validated = RecipientSchema(name=raw_name, email=raw_email)
            cert_docs.append(
                {
                    "job_id": None,  # Updated after job insert
                    "certificate_id": cert_id,
                    "recipient_name": validated.name,
                    "recipient_email": str(validated.email),
                    "status": "PENDING",
                    "file_path": None,
                    "error_message": None,
                    "created_at": now_iso,
                    "completed_at": None,
                }
            )
            pending_count += 1
        except ValidationError as ve:
            initial_failure_count += 1
            err_msgs = [
                e["msg"]
                .replace("Value error, ", "")
                .replace("value is not a valid email address: ", "Invalid email: ")
                for e in ve.errors()
            ]
            err_msg = "; ".join(err_msgs)
            display_name = raw_name if raw_name else f"Recipient #{idx}"
            cert_docs.append(
                {
                    "job_id": None,
                    "certificate_id": cert_id,
                    "recipient_name": display_name,
                    "recipient_email": raw_email,
                    "status": "FAILED",
                    "file_path": None,
                    "error_message": err_msg,
                    "created_at": now_iso,
                    "completed_at": now_iso,
                }
            )


    # Determine initial job status
    if pending_count == 0:
        initial_job_status = "FAILED"
    else:
        initial_job_status = "PENDING"

    # 1. Insert Job document
    job_doc = {
        "event_name": request.event_name,
        "certificate_date": cert_date_str,
        "status": initial_job_status,
        "total_count": len(request.recipients),
        "success_count": 0,
        "failure_count": initial_failure_count,
        "created_at": now_iso,
        "started_at": None,
        "completed_at": now_iso if pending_count == 0 else None,
    }

    insert_result = db.jobs.insert_one(job_doc)
    job_id_str = str(insert_result.inserted_id)

    # Update job_id in certificate documents
    for doc in cert_docs:
        doc["job_id"] = job_id_str

    if cert_docs:
        db.certificates.insert_many(cert_docs)

    # 2. Schedule background processing if there are pending valid recipients
    if pending_count > 0:
        background_tasks.add_task(process_bulk_job, job_id_str)

    # 3. Return HTTP 202 response
    return JobCreateResponse(
        job_id=job_id_str,
        status=initial_job_status,
        total=len(request.recipients),
    )


@router.post(
    "/jobs/upload",
    response_model=JobCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create Bulk Certificate Job via Excel/CSV Upload",
    description="Accepts an Excel (.xlsx/.xls) or CSV file containing recipient names and emails, validates recipients individually, and starts background processing.",
)
async def create_job_from_upload(
    background_tasks: BackgroundTasks,
    event_name: str = Form(..., description="Name of the event or course"),
    certificate_date: str = Form(..., description="Date on certificate (YYYY-MM-DD)"),
    file: UploadFile = File(..., description="Excel (.xlsx/.xls) or CSV file"),
):
    event_name_clean = event_name.strip()
    if not event_name_clean:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Event name must not be empty or blank",
                }
            },
        )

    try:
        parsed_date = datetime.strptime(certificate_date.strip(), "%Y-%m-%d").date()
        cert_date_str = parsed_date.isoformat()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": f"Invalid date format '{certificate_date}'. Expected format: YYYY-MM-DD",
                }
            },
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Uploaded file is empty",
                }
            },
        )

    parsed_results, fatal_error = parse_recipients_from_file(file_bytes, file.filename or "uploaded.csv")

    if fatal_error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": fatal_error,
                }
            },
        )

    if not parsed_results:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "No recipient records found in the uploaded file",
                }
            },
        )

    db = get_db()
    now_iso = datetime.now(timezone.utc).isoformat()

    cert_docs = []
    initial_failure_count = 0
    pending_count = 0

    for item in parsed_results:
        cert_id = generate_unique_cert_id()
        if item.is_valid:
            cert_docs.append(
                {
                    "job_id": None,
                    "certificate_id": cert_id,
                    "recipient_name": item.name,
                    "recipient_email": item.email,
                    "status": "PENDING",
                    "file_path": None,
                    "error_message": None,
                    "created_at": now_iso,
                    "completed_at": None,
                }
            )
            pending_count += 1
        else:
            initial_failure_count += 1
            cert_docs.append(
                {
                    "job_id": None,
                    "certificate_id": cert_id,
                    "recipient_name": item.name,
                    "recipient_email": item.email,
                    "status": "FAILED",
                    "file_path": None,
                    "error_message": item.error_message or "Invalid recipient data",
                    "created_at": now_iso,
                    "completed_at": now_iso,
                }
            )

    initial_job_status = "FAILED" if pending_count == 0 else "PENDING"

    # 1. Insert Job document
    job_doc = {
        "event_name": event_name_clean,
        "certificate_date": cert_date_str,
        "status": initial_job_status,
        "total_count": len(parsed_results),
        "success_count": 0,
        "failure_count": initial_failure_count,
        "created_at": now_iso,
        "started_at": None,
        "completed_at": now_iso if pending_count == 0 else None,
    }

    insert_result = db.jobs.insert_one(job_doc)
    job_id_str = str(insert_result.inserted_id)

    for doc in cert_docs:
        doc["job_id"] = job_id_str

    if cert_docs:
        db.certificates.insert_many(cert_docs)

    # 2. Schedule background processing if there are pending valid recipients
    if pending_count > 0:
        background_tasks.add_task(process_bulk_job, job_id_str)

    return JobCreateResponse(
        job_id=job_id_str,
        status=initial_job_status,
        total=len(parsed_results),
    )


@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    summary="Get Generation Job Status and Details",
    description="Retrieves the real-time progress, counters, and individual certificate statuses for a given job.",
)
def get_job_status(job_id: str):
    db = get_db()

    try:
        job_obj_id = ObjectId(job_id)
    except Exception:
        job_obj_id = job_id

    job = db.jobs.find_one({"_id": job_obj_id})
    if not job:
        job = db.jobs.find_one({"_id": job_id})

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "JOB_NOT_FOUND",
                    "message": "Generation job was not found",
                }
            },
        )

    certs_cursor = db.certificates.find(
        {"$or": [{"job_id": job_id}, {"job_id": str(job["_id"])}]}
    )
    certificates_list = list(certs_cursor)

    total = job.get("total_count", 0)
    success = job.get("success_count", 0)
    failed = job.get("failure_count", 0)
    completed_count = success + failed

    progress_percentage = (
        round((completed_count / total) * 100, 2) if total > 0 else 0.0
    )

    cert_summaries = [
        CertificateSummary(
            certificate_id=c.get("certificate_id"),
            recipient_name=c.get("recipient_name"),
            recipient_email=c.get("recipient_email"),
            status=c.get("status"),
            error=c.get("error_message"),
        )
        for c in certificates_list
    ]

    return JobStatusResponse(
        job_id=str(job["_id"]),
        event_name=job.get("event_name"),
        certificate_date=job.get("certificate_date"),
        status=job.get("status"),
        total=total,
        completed=completed_count,
        successful=success,
        failed=failed,
        progress_percentage=progress_percentage,
        certificates=cert_summaries,
    )


@router.get(
    "/jobs/{job_id}/certificates",
    response_model=JobListCertificatesResponse,
    summary="List All Certificates for a Job",
    description="Returns all certificate records associated with the specified job ID.",
)
def get_job_certificates(job_id: str):
    db = get_db()

    try:
        job_obj_id = ObjectId(job_id)
    except Exception:
        job_obj_id = job_id

    job = db.jobs.find_one({"_id": job_obj_id})
    if not job:
        job = db.jobs.find_one({"_id": job_id})

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "JOB_NOT_FOUND",
                    "message": "Generation job was not found",
                }
            },
        )

    certs_cursor = db.certificates.find(
        {"$or": [{"job_id": job_id}, {"job_id": str(job["_id"])}]}
    )
    certificates_list = list(certs_cursor)

    cert_summaries = [
        CertificateSummary(
            certificate_id=c.get("certificate_id"),
            recipient_name=c.get("recipient_name"),
            recipient_email=c.get("recipient_email"),
            status=c.get("status"),
            error=c.get("error_message"),
        )
        for c in certificates_list
    ]

    return JobListCertificatesResponse(
        job_id=str(job["_id"]),
        certificates=cert_summaries,
    )


@router.get(
    "/{certificate_id}",
    summary="Retrieve Generated Certificate PDF",
    description="Downloads the generated PDF file for a certificate if completed, or returns 409 Conflict if processing/failed.",
)
def get_certificate(certificate_id: str):
    db = get_db()

    cert = db.certificates.find_one({"certificate_id": certificate_id})

    if not cert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "CERTIFICATE_NOT_FOUND",
                    "message": f"Certificate with ID '{certificate_id}' was not found",
                }
            },
        )

    cert_status = cert.get("status")

    if cert_status in ("PENDING", "PROCESSING"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "CERTIFICATE_STILL_PROCESSING",
                    "message": "Certificate generation is still in progress",
                }
            },
        )

    if cert_status == "FAILED":
        error_msg = cert.get("error_message") or "Certificate generation failed"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "CERTIFICATE_GENERATION_FAILED",
                    "message": f"Certificate generation failed: {error_msg}",
                }
            },
        )

    if cert_status == "COMPLETED":
        stored_path = cert.get("file_path")
        if stored_path:
            full_path = os.path.abspath(stored_path)
        else:
            full_path = settings.certs_output_dir / f"{certificate_id}.pdf"

        if not os.path.exists(full_path):
            alt_path = settings.certs_output_dir / f"{certificate_id}.pdf"
            if alt_path.exists():
                full_path = alt_path
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error": {
                            "code": "FILE_NOT_FOUND",
                            "message": "Generated certificate file could not be found on server disk",
                        }
                    },
                )

        return FileResponse(
            path=str(full_path),
            media_type="application/pdf",
            filename=f"{certificate_id}.pdf",
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "error": {
                "code": "INVALID_CERTIFICATE_STATE",
                "message": f"Unknown certificate status '{cert_status}'",
            }
        },
    )
