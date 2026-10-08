import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load .env file using python-dotenv if available
try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class Settings(BaseSettings):
        MONGODB_URI: str = "mongodb://localhost:27017"
        DATABASE_NAME: str = "certificate_generator"
        GENERATED_CERTS_DIR: str = "generated_certificates"

        model_config = SettingsConfigDict(
            env_file=str(BASE_DIR / ".env"),
            env_file_encoding="utf-8",
            extra="ignore",
        )

        @property
        def certs_output_dir(self) -> Path:
            path = Path(self.GENERATED_CERTS_DIR)
            if not path.is_absolute():
                path = BASE_DIR / path
            path.mkdir(parents=True, exist_ok=True)
            return path

except ImportError:
    # Fallback when pydantic_settings package is not installed in the IDE interpreter
    class Settings:  # type: ignore
        def __init__(self):
            self.MONGODB_URI: str = os.getenv(
                "MONGODB_URI", "mongodb://localhost:27017"
            )
            self.DATABASE_NAME: str = os.getenv(
                "DATABASE_NAME", "certificate_generator"
            )
            self.GENERATED_CERTS_DIR: str = os.getenv(
                "GENERATED_CERTS_DIR", "generated_certificates"
            )

        @property
        def certs_output_dir(self) -> Path:
            path = Path(self.GENERATED_CERTS_DIR)
            if not path.is_absolute():
                path = BASE_DIR / path
            path.mkdir(parents=True, exist_ok=True)
            return path


settings = Settings()

