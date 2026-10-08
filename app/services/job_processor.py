import logging
from datetime import datetime, timezone
from typing import Optional
from bson import ObjectId

from app.db.mongodb import get_db
from app.services.certificate_generator import CertificateGenerator, certificate_generator_service

logger = logging.getLogger(__name__)


def process_bulk_job(job_id_str: str, generator: Optional[CertificateGenerator] = None):
    """
    Background worker function that processes individual certificate generation
    tasks for a bulk job with strict failure isolation.
    """
    db = get_db()
    generator_svc = generator or certificate_generator_service

    # Convert string to ObjectId if necessary
    try:
        job_object_id = ObjectId(job_id_str)
    except Exception:
        job_object_id = job_id_str

    # 1. Fetch Job Document
    job = db.jobs.find_one({"_id": job_object_id})
    if not job:
        # Fallback search by string _id
        job = db.jobs.find_one({"_id": job_id_str})

    if not job:
        logger.error(f"Job {job_id_str} not found for background processing.")
        return

    # Update job status to PROCESSING
    now_iso = datetime.now(timezone.utc).isoformat()
    db.jobs.update_one(
        {"_id": job["_id"]},
        {"$set": {"status": "PROCESSING", "started_at": now_iso}},
    )

    event_name = job["event_name"]
    certificate_date = job["certificate_date"]

    # 2. Fetch all PENDING certificate records belonging to this job
    certs_cursor = db.certificates.find(
        {
            "$or": [{"job_id": job_id_str}, {"job_id": str(job["_id"])}],
            "status": "PENDING",
        }
    )
    certificates = list(certs_cursor)


    logger.info(f"Processing job {job_id_str} with {len(certificates)} certificates.")

    # 3. Process certificates individually with failure isolation
    for cert in certificates:
        cert_id_db = cert["_id"]
        certificate_id = cert["certificate_id"]
        recipient_name = cert["recipient_name"]

        # Mark certificate as PROCESSING
        db.certificates.update_one(
            {"_id": cert_id_db},
            {"$set": {"status": "PROCESSING"}},
        )

        try:
            # Generate PDF certificate
            file_path = generator_svc.generate(
                recipient_name=recipient_name,
                event_name=event_name,
                certificate_date=certificate_date,
                certificate_id=certificate_id,
            )

            # On success: mark COMPLETED
            completion_time = datetime.now(timezone.utc).isoformat()
            db.certificates.update_one(
                {"_id": cert_id_db},
                {
                    "$set": {
                        "status": "COMPLETED",
                        "file_path": file_path,
                        "error_message": None,
                        "completed_at": completion_time,
                    }
                },
            )
            # Increment job success count atomically
            db.jobs.update_one(
                {"_id": job["_id"]},
                {"$inc": {"success_count": 1}},
            )
            logger.info(f"Certificate {certificate_id} generated successfully.")

        except Exception as exc:
            # On failure: mark FAILED and catch exception without stopping job
            logger.error(f"Error generating certificate {certificate_id}: {exc}", exc_info=True)
            completion_time = datetime.now(timezone.utc).isoformat()
            error_msg = str(exc) or "Certificate generation failed"
            db.certificates.update_one(
                {"_id": cert_id_db},
                {
                    "$set": {
                        "status": "FAILED",
                        "file_path": None,
                        "error_message": error_msg,
                        "completed_at": completion_time,
                    }
                },
            )
            # Increment job failure count atomically
            db.jobs.update_one(
                {"_id": job["_id"]},
                {"$inc": {"failure_count": 1}},
            )

    # 4. Update Final Job Status
    updated_job = db.jobs.find_one({"_id": job["_id"]})
    total = updated_job.get("total_count", 0)
    success = updated_job.get("success_count", 0)
    failed = updated_job.get("failure_count", 0)

    if failed == 0:
        final_status = "COMPLETED"
    elif success > 0:
        final_status = "COMPLETED_WITH_ERRORS"
    else:
        final_status = "FAILED"

    completed_time = datetime.now(timezone.utc).isoformat()
    db.jobs.update_one(
        {"_id": job["_id"]},
        {"$set": {"status": final_status, "completed_at": completed_time}},
    )
    logger.info(f"Job {job_id_str} finished with status '{final_status}'. Success: {success}, Failed: {failed}")
