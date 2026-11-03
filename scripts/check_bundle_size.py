"""Bundle size verification script for Vercel deployment compliance.

Verifies that all dependencies in `requirements.txt` remain well below
Vercel's strict 500 MB uncompressed function limit (target < 400 MB).
Checks that heavy packages (torch, ultralytics, open-clip-torch, cv2, scipy) are excluded.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

FORBIDDEN_PACKAGES = [
    "torch",
    "torchvision",
    "ultralytics",
    "open-clip-torch",
    "opencv-python",
    "opencv-python-headless",
    "scipy",
    "torchaudio",
]

MAX_BUNDLE_MB = 500.0
TARGET_BUNDLE_MB = 400.0


def check_forbidden_packages(req_path: Path) -> list[str]:
    """Ensure no forbidden heavy libraries are present in requirements.txt."""
    found = []
    text = req_path.read_text(encoding="utf-8").lower()
    for pkg in FORBIDDEN_PACKAGES:
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if pkg in line.split("==")[0].split(">=")[0].split("<=")[0].strip():
                found.append(pkg)
    return found


def get_dir_size_mb(path: Path) -> float:
    """Recursively calculate total directory size in megabytes."""
    total_bytes = 0
    for p in path.rglob("*"):
        if p.is_file():
            try:
                total_bytes += p.stat().st_size
            except (OSError, FileNotFoundError):
                pass
    return total_bytes / (1024 * 1024)


def measure_installed_size() -> float:
    """Measure total size of current site-packages matching requirements.txt."""
    import importlib.metadata

    req_file = Path("requirements.txt")
    lines = [
        l.strip()
        for l in req_file.read_text(encoding="utf-8").splitlines()
        if l.strip() and not l.startswith("#")
    ]

    total_mb = 0.0
    print(f"{'Package':<30} | {'Estimated Size':<15}")
    print("-" * 50)

    for line in lines:
        pkg_name = line.split("==")[0].split(">=")[0].split("[")[0].strip()
        try:
            files = importlib.metadata.files(pkg_name)
            if files:
                pkg_bytes = 0
                for f in files:
                    try:
                        p = Path(f.locate())
                        if p.is_file():
                            pkg_bytes += p.stat().st_size
                    except Exception:
                        pass
                mb = pkg_bytes / (1024 * 1024)
                total_mb += mb
                print(f"{pkg_name:<30} | {mb:>8.2f} MB")
            else:
                print(f"{pkg_name:<30} | {'(not found)':>15}")
        except Exception:
            print(f"{pkg_name:<30} | {'(not found)':>15}")

    print("-" * 50)
    print(f"{'Total Measured Bundle':<30} | {total_mb:>8.2f} MB")
    return total_mb


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Vercel bundle size compliance.")
    parser.add_argument(
        "--simulate-install",
        action="store_true",
        help="Run pip install into a temporary directory to measure exact fresh bundle size.",
    )
    args = parser.parse_args()

    req_path = Path("requirements.txt")
    if not req_path.exists():
        print("ERROR: requirements.txt not found.")
        return 1

    print("=" * 60)
    print("PIXELMIND VERCEL BUNDLE SIZE AUDIT")
    print("=" * 60)

    # 1. Check for prohibited packages
    forbidden = check_forbidden_packages(req_path)
    if forbidden:
        print(f"FAILED: Prohibited heavy packages found in requirements.txt: {forbidden}")
        print("Vercel's serverless runtime will reject bundles containing these.")
        return 1
    print("PASS: No heavy deep-learning packages (torch, ultralytics, cv2) found.")

    # 2. Measure bundle size
    if args.simulate_install:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            print(f"\nSimulating pip install into {tmp_path}...")
            cmd = [
                sys.executable,
                "-m",
                "pip",
                "install",
                "-r",
                str(req_path),
                "--target",
                str(tmp_path),
                "--no-compile",
                "--quiet",
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                print(f"Pip simulation error: {res.stderr}")
                return 1
            total_mb = get_dir_size_mb(tmp_path)
            print(f"Simulated Fresh Install Bundle Size: {total_mb:.2f} MB")
    else:
        total_mb = measure_installed_size()

    print(f"\nAudit Result:")
    print(f"  Measured Size : {total_mb:.2f} MB")
    print(f"  Target Budget : {TARGET_BUNDLE_MB:.1f} MB")
    print(f"  Vercel Ceiling: {MAX_BUNDLE_MB:.1f} MB")

    if total_mb > MAX_BUNDLE_MB:
        print(f"\nFAILED: Bundle exceeds Vercel 500 MB limit by {total_mb - MAX_BUNDLE_MB:.2f} MB!")
        return 1
    elif total_mb > TARGET_BUNDLE_MB:
        print(f"\nWARNING: Bundle is below 500 MB limit but exceeds target of 400 MB.")
        return 0
    else:
        print(f"\nSUCCESS: Bundle size ({total_mb:.2f} MB) is well within Vercel's serverless limits!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
