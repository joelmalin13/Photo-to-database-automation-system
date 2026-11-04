"""Automated directory watcher for incoming document photographs.

Monitors the /inbox directory, automatically triggers the processing pipeline,
moves successful records to /processed, routes corrupt or failed files to /failed,
and logs structured diagnostics.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import time
from typing import Optional

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from config.settings import (
    ALLOWED_EXTENSIONS,
    FAILED_DIR,
    INBOX_DIR,
    PROCESSED_DIR,
    logger,
)
from core.pipeline import process_single_image
from db.session import init_db


def process_inbox_file(file_path: Path) -> bool:
    """Process a single file detected in inbox and move to appropriate destination."""
    if file_path.suffix.lower() not in ALLOWED_EXTENSIONS:
        logger.debug("Skipping non-image file in inbox: %s", file_path.name)
        return False

    logger.info("Detected new document photo in inbox: %s", file_path.name)
    # Wait briefly in case file copy is still finishing
    time.sleep(0.5)

    try:
        with open(file_path, "rb") as f:
            image_bytes = f.read()

        result = process_single_image(
            image_bytes=image_bytes,
            filename=file_path.name,
            doc_type="auto",
            auto_save=True,
        )

        if result.error_message:
            logger.error("Processing failed for %s: %s", file_path.name, result.error_message)
            _move_file_safely(file_path, FAILED_DIR)
            _write_error_log(FAILED_DIR / f"{file_path.stem}.error.txt", result.error_message)
            return False

        logger.info(
            "Successfully ingested %s (Doc ID: %s, Hash: %s)",
            file_path.name,
            result.document_id,
            result.image_hash[:10],
        )
        _move_file_safely(file_path, PROCESSED_DIR)
        return True
    except Exception as exc:
        logger.exception("Unexpected error processing inbox file %s: %s", file_path.name, exc)
        _move_file_safely(file_path, FAILED_DIR)
        _write_error_log(FAILED_DIR / f"{file_path.stem}.error.txt", str(exc))
        return False


def _move_file_safely(source: Path, target_dir: Path) -> None:
    """Safely relocate source file to target folder, handling name collisions."""
    target_dir.mkdir(parents=True, exist_ok=True)
    destination = target_dir / source.name
    if destination.exists():
        timestamp = int(time.time())
        destination = target_dir / f"{source.stem}_{timestamp}{source.suffix}"
    try:
        shutil.move(str(source), str(destination))
        logger.info("Moved %s -> %s", source.name, destination.name)
    except Exception as exc:
        logger.error("Could not move %s: %s", source.name, exc)


def _write_error_log(path: Path, message: str) -> None:
    """Persist failure explanation file alongside failed image."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(message)
    except Exception as exc:
        logger.debug("Failed writing error log %s: %s", path, exc)


def scan_inbox_once() -> int:
    """Scan inbox folder once and process all existing files."""
    processed_count = 0
    for child in INBOX_DIR.iterdir():
        if child.is_file() and child.suffix.lower() in ALLOWED_EXTENSIONS:
            if process_inbox_file(child):
                processed_count += 1
    return processed_count


class InboxChangeHandler(FileSystemEventHandler):
    """Watchdog event handler reacting to created files in /inbox."""

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            process_inbox_file(Path(event.src_path))


def run_watcher(continuous: bool = True) -> None:
    """Run directory watcher in either continuous daemon mode or one-off scan."""
    init_db()
    logger.info("SnapBase Inbox Watcher active. Monitoring: %s", INBOX_DIR)

    # Initial scan of existing files
    initial_processed = scan_inbox_once()
    if initial_processed > 0:
        logger.info("Initial scan processed %d file(s).", initial_processed)

    if not continuous:
        logger.info("Single pass complete. Exiting watcher.")
        return

    handler = InboxChangeHandler()
    observer = Observer()
    observer.schedule(handler, str(INBOX_DIR), recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        logger.info("Stopping inbox watcher...")
        observer.stop()
    observer.join()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SnapBase Inbox Auto-Watcher")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run single-pass scan of inbox and exit immediately.",
    )
    args = parser.parse_args()
    run_watcher(continuous=not args.once)
