"""Streamlit Cloud default entrypoint alias for SnapBase.

Executes app.py directly to support Streamlit Cloud's default 'streamlit_app.py' path.
"""

from pathlib import Path
import runpy

# Resolve absolute path to app.py and execute in current context
_app_file = Path(__file__).resolve().parent / "app.py"
runpy.run_path(str(_app_file), run_name="__main__")
