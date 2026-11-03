"""SnapBase root package namespace."""

import sys
from pathlib import Path

# Ensure root directory is on Python system path
_ROOT_DIR = Path(__file__).resolve().parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))
