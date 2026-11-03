"""Global application configuration, environment settings, and directory definitions for PixelMind.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Project directory structure
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = BASE_DIR / "uploads"
ANNOTATED_DIR = DATA_DIR / "annotated"
SAMPLE_DATA_DIR = BASE_DIR / "sample_data"

# Create directories if needed
for directory in [DATA_DIR, UPLOAD_DIR, ANNOTATED_DIR, SAMPLE_DATA_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Database Configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "pixelmind")

DEFAULT_MYSQL_URL = f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
DEFAULT_SQLITE_URL = f"sqlite:///{(DATA_DIR / 'pixelmind.db').as_posix()}"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_MYSQL_URL)

# Vision Model Configuration
YOLO_MODEL_NAME = os.getenv("YOLO_MODEL_NAME", "yolov8n.pt")
CLIP_MODEL_NAME = os.getenv("CLIP_MODEL_NAME", "ViT-B-32")
CLIP_PRETRAINED = os.getenv("CLIP_PRETRAINED", "openai")
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.25"))

# Ingestion constraints
MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

# Optional LLM Integration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Logging Setup
LOG_FILE = DATA_DIR / "pixelmind.log"
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [pixelmind]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
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
    return {"scenes": [], "environments": ["indoor", "outdoor"], "canonical_categories": []}
