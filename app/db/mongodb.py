import logging
import urllib.parse
from typing import Optional
from pymongo import MongoClient, ASCENDING
from pymongo.database import Database

from app.core.config import settings

logger = logging.getLogger(__name__)


def sanitize_mongodb_uri(uri: str) -> str:
    """Safely escapes unencoded '@' characters in database usernames to prevent PyMongo InvalidURI errors."""
    try:
        if "://" in uri and "@" in uri:
            scheme, rest = uri.split("://", 1)
            # Find last @ before options or host
            if "@" in rest:
                userinfo, hostinfo = rest.rsplit("@", 1)
                if ":" in userinfo:
                    username, password = userinfo.split(":", 1)
                    if "@" in username and "%40" not in username:
                        encoded_username = urllib.parse.quote_plus(username)
                        return f"{scheme}://{encoded_username}:{password}@{hostinfo}"
    except Exception:
        pass
    return uri



class MongoDBManager:
    """
    Manages MongoDB client and database connections to ensure
    a single client connection is reused across the application.
    """

    def __init__(self):
        self.client: Optional[MongoClient] = None
        self.db: Optional[Database] = None

    def connect(self, uri: Optional[str] = None, db_name: Optional[str] = None):
        raw_uri = uri or settings.MONGODB_URI
        target_uri = sanitize_mongodb_uri(raw_uri)
        target_db_name = db_name or settings.DATABASE_NAME

        if self.client is None and self.db is None:
            logger.info(f"Initializing MongoDB client for database: {target_db_name}")
            try:
                client = MongoClient(target_uri, serverSelectionTimeoutMS=3000)
                # Test ping to verify active MongoDB connection
                client.admin.command("ping")
                self.client = client
                self.db = self.client[target_db_name]
                self.init_indexes()
                logger.info("Successfully connected to live MongoDB database.")
            except Exception as e:
                logger.warning(
                    f"Could not connect to live MongoDB server at '{target_uri}': {e}. "
                    "Falling back to in-memory MongoDB (mongomock) for seamless local execution."
                )
                try:
                    import mongomock

                    mock_client = mongomock.MongoClient()
                    self.db = mock_client[target_db_name]
                    self.init_indexes()
                    logger.info("In-memory mongomock database initialized successfully.")
                except Exception as mock_err:
                    logger.error(f"Failed to initialize mock database: {mock_err}")
                    raise e




    def set_db(self, custom_db: Database):
        """Allows setting a mock or custom database instance for testing."""
        self.db = custom_db
        self.init_indexes()

    def close(self):
        if self.client:
            logger.info("Closing MongoDB client connection...")
            self.client.close()
            self.client = None
            self.db = None

    def init_indexes(self):
        if self.db is None:
            return
        try:
            self.db.jobs.create_index([("status", ASCENDING)])
            self.db.certificates.create_index([("job_id", ASCENDING)])
            self.db.certificates.create_index(
                [("certificate_id", ASCENDING)], unique=True
            )
            logger.info("MongoDB indexes created successfully.")
        except Exception as e:
            logger.warning(f"Failed to create MongoDB indexes: {e}")

    def get_db(self) -> Database:
        if self.db is None:
            self.connect()
        return self.db


db_manager = MongoDBManager()


def get_db() -> Database:
    return db_manager.get_db()
