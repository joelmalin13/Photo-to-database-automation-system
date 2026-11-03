"""Database engine setup, initialization, and connection lifecycle.

Supports MySQL (via mysql-connector-python) with automatic fallback to SQLite
if MySQL is unreachable, ensuring zero downtime and resilient startup.
"""

from __future__ import annotations

from contextlib import contextmanager
import re
from typing import Any, Dict, Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from config.settings import (
    DATABASE_URL,
    DEFAULT_MYSQL_URL,
    DEFAULT_SQLITE_URL,
    logger,
)
from db.models import Base

# Database status tracking state
_db_status: Dict[str, Any] = {
    "engine_name": "unknown",
    "is_fallback": False,
    "connected": False,
    "message": "",
    "url_masked": "",
}


def _mask_url(url: str) -> str:
    """Mask password credentials in database connection URI."""
    return re.sub(r":([^:@]+)@", ":****@", url)


def create_resilient_engine() -> Engine:
    """Attempt connecting to configured MySQL; automatically fall back to SQLite if unreachable."""
    global _db_status
    target_url = DATABASE_URL

    # If test memory URL requested, return directly
    if target_url.startswith("sqlite:///:memory:"):
        _db_status = {
            "engine_name": "SQLite (In-Memory)",
            "is_fallback": False,
            "connected": True,
            "message": "Connected to in-memory test database.",
            "url_masked": "sqlite:///:memory:",
        }
        return create_engine(
            target_url,
            connect_args={"check_same_thread": False},
            echo=False,
        )

    # Attempt MySQL first if target URL is mysql
    if target_url.startswith("mysql"):
        try:
            logger.info("Attempting connection to MySQL: %s", _mask_url(target_url))
            mysql_engine = create_engine(
                target_url,
                pool_pre_ping=True,
                pool_recycle=3600,
                echo=False,
            )
            # Test ping
            with mysql_engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            _db_status = {
                "engine_name": "MySQL 8.0+",
                "is_fallback": False,
                "connected": True,
                "message": "Connected to MySQL server (photo_automation).",
                "url_masked": _mask_url(target_url),
            }
            logger.info("MySQL database connection verified successfully.")
            return mysql_engine

        except Exception as exc:
            logger.warning(
                "MySQL is unreachable (%s). Initiating automatic fallback to local SQLite.",
                exc,
            )
            _db_status = {
                "engine_name": "SQLite (Fallback)",
                "is_fallback": True,
                "connected": True,
                "message": f"MySQL server unreachable ({str(exc).splitlines()[0]}). Falling back to SQLite.",
                "url_masked": _mask_url(DEFAULT_SQLITE_URL),
            }

    # SQLite fallback / default
    sqlite_engine = create_engine(
        DEFAULT_SQLITE_URL,
        connect_args={"check_same_thread": False},
        echo=False,
    )
    if not _db_status.get("engine_name") or _db_status["engine_name"] == "unknown":
        _db_status = {
            "engine_name": "SQLite",
            "is_fallback": False,
            "connected": True,
            "message": "Connected to local SQLite database.",
            "url_masked": _mask_url(DEFAULT_SQLITE_URL),
        }
    return sqlite_engine


engine = create_resilient_engine()
SessionFactory = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db_status() -> Dict[str, Any]:
    """Return runtime connection health and engine identity for the Settings page."""
    return dict(_db_status)


def init_db() -> None:
    """Initialize database tables idempotently at startup."""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info(
            "Database initialized successfully on %s",
            _db_status.get("engine_name", "database"),
        )
    except Exception as exc:
        logger.error("Failed to initialize database tables: %s", exc)
        raise


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Provide a transactional database session context manager."""
    session: Session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.error("Transaction rolled back due to exception: %s", exc)
        raise
    finally:
        session.close()
