# Bulk Certificate Generator Backend

A high-performance, asynchronous backend application built with **FastAPI**, **MongoDB Atlas**, **Pydantic**, and **ReportLab** to process bulk certificate generation requests with real-time job tracking, resilient per-recipient failure isolation, Excel/CSV file upload support, and secure PDF retrieval.

---

## Architecture Overview

```text
Client (Web UI / REST API / Swagger)
   │
   ├── Option A: HTTP POST /api/v1/certificates/jobs (JSON Payload)
   ├── Option B: HTTP POST /api/v1/certificates/jobs/upload (Excel .xlsx / CSV Upload)
   ▼
FastAPI Request Handler & Resilient Recipient Parser
   │
   ├── 1. Validates Recipient Data Individually (Isolates Invalid Emails/Names)
   ├── 2. Persists Job Document (Status: PENDING / COMPLETED_WITH_ERRORS)
   ├── 3. Persists Certificate Documents (Status: PENDING for valid, FAILED for invalid)
   ├── 4. Returns HTTP 202 Accepted with job_id
   ▼
MongoDB Atlas / PyMongo Client (Single Reused Connection w/ Smart In-Memory Fallback)
   │
   ▼
FastAPI Background Tasks (Job Processor)
   │
   ├── Iterates through PENDING certificate records
   ├── Strict Try-Except Failure Isolation
   ▼
Certificate Generator Service (ReportLab PDF Engine)
   │
   ├── Generates Vector PDF: generated_certificates/{certificate_id}.pdf
   ├── Updates Certificate Document (Status: COMPLETED / FAILED)
   └── Atomically updates Job Document Counters ($inc: success_count/failure_count)
   │
   ▼
Final Job Completion (Status: COMPLETED / COMPLETED_WITH_ERRORS / FAILED)
```

---

## Key Features

- **Asynchronous HTTP 202 Execution**: Instantly responds with `job_id` without blocking HTTP clients during heavy batch PDF rendering.
- **Resilient Recipient Failure Isolation**: Invalid emails (missing `@` sign, malformed syntax) or generation exceptions for single recipients do **not** reject or halt the bulk batch. Valid recipients proceed to have PDFs rendered while invalid ones display exact failure reasons.
- **Excel (.xlsx/.xls) & CSV (.csv) Upload**: Native file parser automatically identifies column headers (`Name`, `Full Name`, `Email`, `Email Address`) and imports batch recipients effortlessly.
- **Smart MongoDB Connection Fallback**: Automatically connects to MongoDB Atlas using PyMongo. If Atlas is unreachable or unconfigured locally, falls back seamlessly to an in-memory database (`mongomock`) for offline zero-friction execution.
- **MongoDB Normalized Schema**: Separate `jobs` and `certificates` collections avoid document size limits and allow efficient per-recipient status updates.
- **ReportLab PDF Rendering**: Generates clean, vector-rendered certificates stored safely on disk and served as standard `application/pdf` streams.
- **Comprehensive Test Suite**: 18 passing `pytest` tests covering validation, file uploads, progress tracking, failure isolation, and retrieval.
- **Minimal Demonstration UI**: Simple vanilla HTML/CSS/JS interface included for live demonstration, file uploads, and status polling.

---

## Tech Stack

- **Language**: Python 3.11+
- **Framework**: FastAPI
- **Database**: MongoDB Atlas (PyMongo) with `mongomock` fallback
- **Data Validation**: Pydantic v2 & Email Validator
- **File Processing**: OpenPyXL & CSV engine
- **PDF Engine**: ReportLab
- **Testing**: Pytest, Mongomock, HTTPX

---

## Project Structure

```text
bulk-certificate-generator/
│
├── app/
│   ├── main.py                     # FastAPI app, lifespan manager & custom 500/422 exception handlers
│   ├── api/
│   │   └── routes/
│   │       └── certificates.py     # REST API routes (JSON creation, File Upload, Status, Retrieval)
│   ├── schemas/
│   │   ├── job.py                  # Pydantic schemas for Job request/response
│   │   └── certificate.py          # Pydantic schemas for Certificate response
│   ├── services/
│   │   ├── certificate_generator.py# ReportLab service wrapper
│   │   ├── job_processor.py        # Background worker & failure isolation logic
│   │   └── file_parser.py          # Excel (.xlsx/.xls) and CSV (.csv) row parser
│   ├── db/
│   │   └── mongodb.py              # Single PyMongo connection manager, URI sanitizer & mongomock fallback
│   └── core/
│       └── config.py               # Application settings & environment variables
│
├── templates/
│   └── certificate_template.py     # Vector PDF layout, typography, borders, and graphics
│
├── generated_certificates/          # PDF file storage output directory
│
├── frontend/                       # Demonstration UI (Vanilla HTML/CSS/JS)
│   ├── index.html
│   ├── style.css
│   └── app.js
│
├── tests/                          # Pytest test suite
│   ├── conftest.py
│   ├── test_jobs.py
│   ├── test_validation.py
│   ├── test_upload.py
│   ├── test_generation.py
│   ├── test_status.py
│   ├── test_failure_handling.py
│   └── test_retrieval.py
│
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
└── pytest.ini
```

---

## Getting Started

### 1. Prerequisites

- Python 3.11 or higher
- MongoDB Atlas cluster (or fallback in-memory database)

### 2. Installation

Clone the repository and install dependencies:

```bash
# Clone the repository
git clone <repository_url>
cd Bulk_Certificates

# Create and activate virtual environment
python -m venv venv

# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install required packages
pip install -r requirements.txt
```

### 3. Environment Setup & MongoDB Atlas Connection

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env` with your MongoDB Atlas database credentials:

```env
MONGODB_URI=mongodb+srv://<db_username>:<db_password>@cluster0.68h9uuc.mongodb.net/?retryWrites=true&w=majority
DATABASE_NAME=certificate_generator
GENERATED_CERTS_DIR=generated_certificates
```

> **Note**: Ensure `<db_username>` is the **Database User** created under *Security -> Database Access* in MongoDB Atlas (not your account email address).

---

## Running the Application

Start the server using `uvicorn`:

```bash
uvicorn app.main:app --reload
```

Access the endpoints:
- **Interactive UI**: [http://localhost:8000/](http://localhost:8000/)
- **Swagger OpenAPI Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc Docs**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## Running Tests

The test suite runs 18 automated tests covering input validation, Excel/CSV parsing, PDF generation, failure isolation, and retrieval:

```bash
pytest
```

---

## REST API Specification

### 1. Create Bulk Generation Job (JSON)
`POST /api/v1/certificates/jobs`

**Request Body**:
```json
{
  "event_name": "Python Workshop",
  "certificate_date": "2026-10-08",
  "recipients": [
    {
      "name": "John Doe",
      "email": "john@example.com"
    },
    {
      "name": "Invalid User",
      "email": "bad-email-no-at-sign"
    }
  ]
}
```

**Response (`202 Accepted`)**:
```json
{
  "job_id": "66f2a71d8f...",
  "status": "PENDING",
  "total": 2
}
```

---

### 2. Create Bulk Generation Job (Excel / CSV Upload)
`POST /api/v1/certificates/jobs/upload`

**Form Data Parameters**:
- `event_name`: `"Python Workshop"`
- `certificate_date`: `"2026-10-08"`
- `file`: Uploaded Excel file (`.xlsx` / `.xls`) or CSV (`.csv`) containing `Name` and `Email` headers.

**Response (`202 Accepted`)**:
```json
{
  "job_id": "66f2a71d8f...",
  "status": "PENDING",
  "total": 2
}
```

---

### 3. Get Job Status & Progress
`GET /api/v1/certificates/jobs/{job_id}`

**Response (`200 OK`)**:
```json
{
  "job_id": "66f2a71d8f...",
  "event_name": "Python Workshop",
  "certificate_date": "2026-10-08",
  "status": "COMPLETED_WITH_ERRORS",
  "total": 2,
  "completed": 2,
  "successful": 1,
  "failed": 1,
  "progress_percentage": 100.0,
  "certificates": [
    {
      "certificate_id": "CERT-7F92A1C4",
      "recipient_name": "John Doe",
      "recipient_email": "john@example.com",
      "status": "COMPLETED",
      "error": null
    },
    {
      "certificate_id": "CERT-3B81D9E0",
      "recipient_name": "Invalid User",
      "recipient_email": "bad-email-no-at-sign",
      "status": "FAILED",
      "error": "Invalid email: An email address must have an @-sign."
    }
  ]
}
```

---

### 4. List Job Certificates
`GET /api/v1/certificates/jobs/{job_id}/certificates`

---

### 5. Retrieve Certificate PDF
`GET /api/v1/certificates/{certificate_id}`

- **If COMPLETED**: Returns PDF stream (`Content-Type: application/pdf`).
- **If PROCESSING / PENDING**: Returns `409 Conflict` with `"Certificate generation is still in progress"`.
- **If FAILED**: Returns `409 Conflict` with `"Certificate generation failed: <reason>"`.
- **If NOT FOUND**: Returns `404 Not Found`.

---

## Example cURL Commands

```bash
# 1. Submit a JSON bulk generation job
curl -X POST "http://localhost:8000/api/v1/certificates/jobs" \
     -H "Content-Type: application/json" \
     -d '{
           "event_name": "FastAPI Masterclass",
           "certificate_date": "2026-10-08",
           "recipients": [
             {"name": "John Doe", "email": "john@example.com"},
             {"name": "Alice Smith", "email": "alice@example.com"}
           ]
         }'

# 2. Submit an Excel file upload job
curl -X POST "http://localhost:8000/api/v1/certificates/jobs/upload" \
     -F "event_name=Python Workshop" \
     -F "certificate_date=2026-10-08" \
     -F "file=@recipients.xlsx"

# 3. Check job status
curl "http://localhost:8000/api/v1/certificates/jobs/66f2a71d8f..."

# 4. Download generated PDF
curl -O "http://localhost:8000/api/v1/certificates/CERT-7F92A1C4"
```

---

## Design Decisions & Architectural Rationale

### 1. Why Asynchronous Processing (`202 Accepted`)?
Generating PDFs involves graphics rendering, layout engine computation, and filesystem writes. Synchronously generating 100+ PDFs inside a single HTTP request would cause browser timeouts, gateway timeouts (HTTP 504), and poor user experience. Returning `202 Accepted` immediately gives clients a `job_id` to track progress asynchronously.

### 2. Why MongoDB Atlas?
MongoDB provides flexible, schema-free JSON document storage ideal for job metadata and status tracking. PyMongo allows direct control over atomic updates (`$inc`, `$set`) and explicit index creation without heavy ORM overhead.

### 3. Why Separate `jobs` and `certificates` Collections?
Embedding thousands of certificate objects inside a single `job` document risks hitting MongoDB's 16MB document size limit and causes expensive document growth during concurrent updates. Decoupling into two collections:
- Prevents document size bloat
- Allows atomic per-certificate status updates (`$set`, `$inc`)
- Enables efficient querying and indexing (`certificates.job_id`, `certificates.certificate_id`)

### 4. Why Local Filesystem Storage for this Assignment?
Storing binary PDF blobs in MongoDB bloats database size and slows queries. For this application, saving PDFs locally in `generated_certificates/` keeps the implementation simple, dependency-free, and easy to run locally.

### 5. Why Lightweight Background Processing & In-Memory Fallback?
FastAPI's built-in `BackgroundTasks` mechanism executes in the same Python process loop, avoiding external infrastructure dependencies (like Redis, RabbitMQ, or Celery) while remaining completely transparent. The `mongomock` database fallback allows developers to test the application instantly offline without setup hurdles.

---

## Scalability & Production Evolution

If this system evolves to process millions of certificates daily in production:

1. **Distributed Queue**: Replace FastAPI `BackgroundTasks` with **Celery + Redis** or **AWS SQS + Workers** for distributed task queues across multiple worker nodes.
2. **Cloud Object Storage**: Save generated PDFs directly to **Amazon S3** or **Google Cloud Storage** with presigned download URLs rather than local disk.
3. **Database Migration / Sharding**: MongoDB collections can be sharded on `job_id` or `certificate_id` for horizontal database scaling. Alternatively, PostgreSQL with `JSONB` could be introduced if relational transaction guarantees are required.
4. **Rate Limiting & Authentication**: Add OAuth2/JWT authentication middleware and API rate limiting via Redis (`slowapi`).
5. **Retry Mechanisms**: Implement exponential backoff retries for transient rendering or network failures.

---

## Interview Demonstration Guide

Be prepared to explain the following key aspects during an interview:

1. **Job Creation**: `POST /api/v1/certificates/jobs` validates input using Pydantic, inserts a `job` record (`PENDING`) and `N` `certificate` records (`PENDING`), schedules a background task, and immediately returns HTTP 202 with `job_id`.
2. **File Upload Parsing**: `POST /api/v1/certificates/jobs/upload` accepts `.xlsx` / `.csv` files, parses rows using OpenPyXL/CSV, extracts headers dynamically, and creates job records.
3. **Resilient Failure Isolation**: Invalid emails are isolated during recipient parsing so valid recipients still receive certificates. Background PDF generation errors are caught per-recipient in a `try...except` block, updating only that record's `error_message`.
4. **Data Modeling**: `jobs` stores aggregate metrics (`total_count`, `success_count`, `failure_count`), while `certificates` stores individual recipient states linked via `job_id`.
5. **Certificate Retrieval**: `GET /api/v1/certificates/{certificate_id}` streams the generated PDF if `COMPLETED`, or returns `409 Conflict` if processing or failed with exact failure reasons.
