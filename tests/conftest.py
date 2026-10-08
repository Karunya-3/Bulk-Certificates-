import os
import shutil
import tempfile
import pytest
from fastapi.testclient import TestClient
import mongomock

from app.main import app
from app.db.mongodb import db_manager
from app.core.config import settings


@pytest.fixture(autouse=True)
def setup_mock_db(tmp_path):
    """
    Fixture that automatically overrides the MongoDB database instance with a clean mongomock database
    and configures a temporary directory for output certificate PDFs for every test.
    """
    # Override database with mongomock instance
    mock_client = mongomock.MongoClient()
    mock_db = mock_client["test_certificate_generator"]
    db_manager.set_db(mock_db)

    # Override certs output directory to temporary folder
    temp_certs_dir = tmp_path / "generated_certificates"
    temp_certs_dir.mkdir(parents=True, exist_ok=True)
    original_output_dir = settings.GENERATED_CERTS_DIR
    settings.GENERATED_CERTS_DIR = str(temp_certs_dir)

    yield mock_db

    # Reset
    settings.GENERATED_CERTS_DIR = original_output_dir


@pytest.fixture
def client():
    """Returns a TestClient instance for testing FastAPI endpoints."""
    return TestClient(app)
