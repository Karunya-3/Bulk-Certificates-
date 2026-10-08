import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import certificates
from app.core.config import settings
from app.db.mongodb import db_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("bulk_certificates")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Connect to MongoDB and ensure indexes
    logger.info("Initializing MongoDB connection on app startup...")
    db_manager.connect()

    # Ensure output directory exists
    _ = settings.certs_output_dir

    yield

    # Shutdown: Close MongoDB connection
    logger.info("Closing MongoDB connection on app shutdown...")
    db_manager.close()


app = FastAPI(
    title="Bulk Certificate Generator API",
    description="Backend API for high-throughput bulk certificate generation, job progress tracking, and failure isolation.",
    version="1.0.0",
    lifespan=lifespan,
)

# Register API Router
app.include_router(certificates.router)


# Custom Error Handlers to guarantee consistent JSON error formatting
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)

    error_code = "HTTP_ERROR"
    if exc.status_code == 404:
        error_code = "NOT_FOUND"
    elif exc.status_code == 409:
        error_code = "CONFLICT"
    elif exc.status_code == 400:
        error_code = "BAD_REQUEST"

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": error_code,
                "message": str(exc.detail),
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        loc = " -> ".join([str(x) for x in error.get("loc", [])])
        errors.append(f"{loc}: {error.get('msg')}")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Input validation failed for request body",
                "details": errors,
            }
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled server error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": f"Server error: {str(exc)}",
            }
        },
    )


# Serve minimal frontend

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/", include_in_schema=False)
async def serve_index():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return JSONResponse({"message": "Bulk Certificate Generator API is running. Visit /docs for Swagger UI."})
