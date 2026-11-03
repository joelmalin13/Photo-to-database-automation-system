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
INBOX_DIR: Path = BASE_DIR / "inbox"
PROCESSED_DIR: Path = BASE_DIR / "processed"
FAILED_DIR: Path = BASE_DIR / "failed"
LOGS_DIR: Path = DATA_DIR / "logs"

# Ensure runtime directories exist
for directory in (
    DATA_DIR,
    UPLOAD_DIR,
    INBOX_DIR,
    PROCESSED_DIR,
    FAILED_DIR,
    LOGS_DIR,
):
    directory.mkdir(parents=True, exist_ok=True)

# Database settings
DB_PATH: Path = DATA_DIR / "snapbase.db"
DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH.as_posix()}")

# API and Model configurations
GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
DEFAULT_ENGINE: str = os.getenv(
    "DEFAULT_ENGINE", "gemini" if GEMINI_API_KEY else "ocr"
)

# Processing parameters
CONFIDENCE_THRESHOLD: float = 0.70
MAX_IMAGE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB limit
ALLOWED_EXTENSIONS: set[str] = {".jpg", ".jpeg", ".png", ".webp"}

# UI Palette and styling constants
THEME_PRIMARY: str = "#C62828"
THEME_SECONDARY: str = "#111111"
THEME_BACKGROUND: str = "#FFFFFF"
THEME_TEXT: str = "#1F1F1F"
THEME_BORDER: str = "#E5E5E5"
THEME_STATUS_PROCESSED: str = "#2E7D32"
THEME_STATUS_PENDING: str = "#F57C00"
THEME_STATUS_REJECTED: str = "#C62828"


class DocumentStatus(str, Enum):
    """Lifecycle statuses for captured and processed documents."""

    PENDING = "pending"
    PROCESSED = "processed"
    REJECTED = "rejected"


class DocumentType(str, Enum):
    """Recognized document classifications."""

    RECEIPT_INVOICE = "receipt_invoice"
    STUDENT_ID_FORM = "student_id_form"
    GENERIC_TABLE = "generic_table"
    AUTO = "auto"


def load_schemas() -> Dict[str, Any]:
    """Load and parse document field schemas from config/schemas.json.

    Returns:
        Dict[str, Any]: Mapping of document type to its configuration schema.
    """
    schemas_file = CONFIG_DIR / "schemas.json"
    if not schemas_file.exists():
        raise FileNotFoundError(f"Schema file not found at {schemas_file}")
    with open(schemas_file, "r", encoding="utf-8") as f:
        return json.load(f)


def setup_logger(name: str = "snapbase") -> logging.Logger:
    """Configure a unified logger with both console and rotating file output.

    Args:
        name: Name of the logger instance.

    Returns:
        logging.Logger: Preconfigured logger instance.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler
    log_file = LOGS_DIR / "snapbase.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


logger = setup_logger()
