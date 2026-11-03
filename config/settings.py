"""Global application configuration, environment settings, and directory definitions for PixelMind.

Supports dual operating modes:
- Cloud Mode (Vercel Serverless): Gemini 2.5 Flash, Supabase Storage, Hosted DB (Postgres/MySQL)
- Local Mode (Desktop/Server): YOLOv8n, OpenCLIP ViT-B-32, Local Storage, SQLite/MySQL
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import tempfile
from typing import Any, Dict
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Detect environment
IS_VERCEL = bool(os.getenv("VERCEL"))
AI_MODE = os.getenv("AI_MODE", "cloud" if IS_VERCEL else "local").strip().lower()

# Directory structure
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
PUBLIC_DIR = BASE_DIR / "public"

# Writable directory configuration: /tmp for serverless, local directories for workstation
if IS_VERCEL:
    TMP_ROOT = Path("/tmp")
else:
    TMP_ROOT = Path(tempfile.gettempdir())

if IS_VERCEL or AI_MODE == "cloud":
    DATA_DIR = TMP_ROOT / "pixelmind_data"
    UPLOAD_DIR = TMP_ROOT / "pixelmind_uploads"
    ANNOTATED_DIR = TMP_ROOT / "pixelmind_annotated"
else:
    DATA_DIR = BASE_DIR / "data"
    UPLOAD_DIR = BASE_DIR / "uploads"
    ANNOTATED_DIR = DATA_DIR / "annotated"

SAMPLE_DATA_DIR = BASE_DIR / "sample_data"

# Ensure directories exist where permitted
try:
    for directory in [DATA_DIR, UPLOAD_DIR, ANNOTATED_DIR]:
        directory.mkdir(parents=True, exist_ok=True)
except Exception:
    pass

# Database Configuration
# Supports Supabase / Neon PostgreSQL (psycopg), MySQL (pymysql / mysql-connector), and SQLite
DB_URL = os.getenv("DB_URL") or os.getenv("DATABASE_URL")
DEFAULT_SQLITE_URL = f"sqlite:///{(DATA_DIR / 'pixelmind.db').as_posix()}"

# Cloud AI Configuration (Google Gemini)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "text-embedding-004")

# Supabase Storage Configuration (Cloud Storage)
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "supabase" if (IS_VERCEL or AI_MODE == "cloud") else "local").lower()
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "pixelmind-images")

# Local AI Configuration (YOLO & CLIP)
YOLO_MODEL_NAME = os.getenv("YOLO_MODEL_NAME", "yolov8n.pt")
CLIP_MODEL_NAME = os.getenv("CLIP_MODEL_NAME", "ViT-B-32")
CLIP_PRETRAINED = os.getenv("CLIP_PRETRAINED", "openai")
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.25"))

# Ingestion constraints: 4 MB limit in cloud mode (under Vercel 4.5 MB request ceiling)
if IS_VERCEL or AI_MODE == "cloud":
    MAX_FILE_SIZE_BYTES = 4 * 1024 * 1024  # 4 MB
else:
    MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

# Logging setup (StreamHandler for all; FileHandler only if local disk is writable)
handlers: list[logging.Handler] = [logging.StreamHandler()]
if not IS_VERCEL and AI_MODE != "cloud":
    try:
        log_file = DATA_DIR / "pixelmind.log"
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [pixelmind]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=handlers,
)
logger = logging.getLogger("pixelmind")


def load_categories_config() -> Dict[str, str]:
    """Load label-to-category mapping from config/categories.json."""
    cat_file = CONFIG_DIR / "categories.json"
    if cat_file.exists():
        with open(cat_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def load_scenes_config() -> Dict[str, Any]:
    """Load scene definitions and environments from config/scenes.json."""
    scene_file = CONFIG_DIR / "scenes.json"
    if scene_file.exists():
        with open(scene_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "scenes": [],
        "environments": ["indoor", "outdoor"],
        "canonical_categories": [
            "Nature",
            "Animals",
            "Vehicles",
            "Technology",
            "Food",
            "Architecture",
            "Human activities",
            "Sports",
            "Electronics",
        ],
    }
