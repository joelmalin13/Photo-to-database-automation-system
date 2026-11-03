"""Application configuration and centralized settings for SnapBase.

Provides directory paths, environment variable access, schema loaders,
status enums, and structured logging configuration.
"""

from __future__ import annotations

from enum import Enum
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Base project directories
BASE_DIR: Path = Path(__file__).resolve().parent.parent
CONFIG_DIR: Path = BASE_DIR / "config"
DATA_DIR: Path = BASE_DIR / "data"
UPLOAD_DIR: Path = DATA_DIR / "uploads"
PROCESSED_DIR: Path = DATA_DIR / "processed"
INBOX_DIR: Path = BASE_DIR / "inbox"
FAILED_DIR: Path = BASE_DIR / "failed"
LOGS_DIR: Path = DATA_DIR / "logs"

# Ensure runtime directories exist
for directory in (
    DATA_DIR,
    UPLOAD_DIR,
    PROCESSED_DIR,
    INBOX_DIR,
    FAILED_DIR,
    LOGS_DIR,
):
    directory.mkdir(parents=True, exist_ok=True)

# Database credentials & URL configuration
DB_USER: str = os.getenv("DB_USER", "root")
DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
DB_HOST: str = os.getenv("DB_HOST", "localhost")
DB_PORT: str = os.getenv("DB_PORT", "3306")
DB_NAME: str = os.getenv("DB_NAME", "photo_automation")

# Default MySQL connection string using mysql-connector-python
DEFAULT_MYSQL_URL: str = (
    f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# SQLite fallback path
SQLITE_DB_PATH: Path = DATA_DIR / "snapbase.db"
DEFAULT_SQLITE_URL: str = f"sqlite:///{SQLITE_DB_PATH.as_posix()}"

# Final configured DATABASE_URL (defaults to MySQL string, checked at runtime in db/session.py)
DATABASE_URL: str = os.getenv("DATABASE_URL", DEFAULT_MYSQL_URL)

# OCR and Extraction Engine settings
# Specification: Default engine is EasyOCR; Tesseract & Gemini are optional via settings
DEFAULT_ENGINE: str = os.getenv("DEFAULT_ENGINE", "ocr")  # 'ocr' (EasyOCR), 'tesseract', or 'gemini'
GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
TESSERACT_CMD: str | None = os.getenv("TESSERACT_CMD")

# Processing parameters
CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.70"))
MAX_IMAGE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB limit
ALLOWED_EXTENSIONS: set[str] = {".jpg", ".jpeg", ".png", ".webp"}

# UI Palette and styling constants
THEME_PRIMARY: str = "#C62828"
THEME_SECONDARY: str = "#111111"
THEME_BACKGROUND: str = "#FFFFFF"
THEME_TEXT: str = "#111827"
THEME_BORDER: str = "#E5E7EB"


class DocumentStatus(str, Enum):
    """Lifecycle statuses matching official specification."""

    UPLOADED = "uploaded"
    PROCESSED = "processed"
    VERIFIED = "verified"
    REJECTED = "rejected"
    FAILED = "failed"
    # Aliases for backwards compatibility with earlier components
    PENDING = "processed"


class DocumentCategory(str, Enum):
    """Normalized document categories matching official schema."""

    RECEIPTS = "receipts"
    STUDENTS = "students"
    BUSINESS_CARDS = "business_cards"
    OTHER = "other"


def load_schemas() -> Dict[str, Any]:
    """Load and parse document field schemas from config/schemas.json."""
    schemas_file = CONFIG_DIR / "schemas.json"
    if not schemas_file.exists():
        raise FileNotFoundError(f"Schema file not found at {schemas_file}")
    with open(schemas_file, "r", encoding="utf-8") as f:
        return json.load(f)


def setup_logger(name: str = "snapbase") -> logging.Logger:
    """Configure unified logger with both console and rotating file output."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    log_file = LOGS_DIR / "snapbase.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


logger = setup_logger()
