"""Database engine setup, initialization, and connection lifecycle management.

Supports:
- PostgreSQL (Supabase / Neon) via psycopg[binary]
- MySQL via pymysql / mysql-connector
- SQLite for local development and in-memory testing
- Serverless-safe NullPool on Vercel to prevent connection exhaustion
"""

from __future__ import annotations

from contextlib import contextmanager
import os
import re
import threading
from typing import Any, Dict, Generator
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

from config.settings import (
    AI_MODE,
    DB_URL,
    DEFAULT_SQLITE_URL,
    IS_VERCEL,
    logger,
)
from db.models import Base

# Global database health status tracking
_db_status: Dict[str, Any] = {
    "engine_name": "unknown",
    "is_fallback": False,
    "connected": False,
    "message": "",
    "url_masked": "",
}

_init_lock = threading.Lock()
_tables_initialized = False


def _mask_url(url: str) -> str:
    """Mask sensitive database credentials in URI string."""
    return re.sub(r":([^:@]+)@", ":****@", url)


def _normalize_db_url(raw_url: str) -> str:
    """Normalize connection string prefixes to standard drivers."""
    url = raw_url.strip()
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://") and not url.startswith("postgresql+"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    if url.startswith("mysql://"):
        return "mysql+pymysql://" + url[len("mysql://"):]
    return url


def create_resilient_engine() -> Engine:
    """Initialize database engine based on environment and connectivity."""
    global _db_status
    raw_url = DB_URL or ""

    # 1. In-memory test database
    if raw_url.startswith("sqlite:///:memory:") or os.getenv("TESTING") == "1":
        _db_status = {
            "engine_name": "SQLite (In-Memory)",
            "is_fallback": False,
            "connected": True,
            "message": "Connected to in-memory test database.",
            "url_masked": "sqlite:///:memory:",
        }
        return create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False,
        )

    # 2. Hosted DB URL (PostgreSQL / MySQL)
    if raw_url:
        target_url = _normalize_db_url(raw_url)
        masked = _mask_url(target_url)
        is_cloud_env = IS_VERCEL or (AI_MODE == "cloud")

        try:
            logger.info("Connecting to hosted database: %s", masked)
            engine_kwargs: Dict[str, Any] = {
                "pool_pre_ping": True,
                "echo": False,
            }
            if is_cloud_env and not target_url.startswith("sqlite"):
                # Use NullPool for serverless lambda environments to prevent connection leaks
                engine_kwargs["poolclass"] = NullPool
            else:
                engine_kwargs["pool_recycle"] = 3600

            cloud_engine = create_engine(target_url, **engine_kwargs)

            # Test active connection ping
            with cloud_engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            engine_type = "PostgreSQL" if "postgres" in target_url else ("MySQL" if "mysql" in target_url else "SQL Database")
            _db_status = {
                "engine_name": engine_type,
                "is_fallback": False,
                "connected": True,
                "message": f"Connected to hosted {engine_type} database.",
                "url_masked": masked,
            }
            logger.info("%s database connection established.", engine_type)
            return cloud_engine

        except Exception as exc:
            logger.error("Failed connecting to configured DB_URL (%s): %s", masked, exc)
            if is_cloud_env:
                _db_status = {
                    "engine_name": "Database Connection Failed",
                    "is_fallback": False,
                    "connected": False,
                    "message": f"Could not connect to hosted DB: {str(exc).splitlines()[0]}",
                    "url_masked": masked,
                }
                raise RuntimeError(
                    f"Cloud mode database connection failed ({exc}). Please verify DB_URL in environment variables."
                ) from exc

    # 3. Cloud mode without DB_URL must give a clear error and never silently use SQLite
    if (IS_VERCEL or AI_MODE == "cloud") and not raw_url:
        _db_status = {
            "engine_name": "Hosted DB Required",
            "is_fallback": False,
            "connected": False,
            "message": "Cloud mode requires DB_URL (Supabase/Neon PostgreSQL or MySQL). Silent SQLite fallback is disabled.",
            "url_masked": "",
        }
        logger.error("DB_URL missing in cloud mode. Silent SQLite fallback is disabled.")

        def _cloud_db_unconfigured_creator(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError(
                "Cloud mode database error: DB_URL is not set. In cloud/serverless mode, "
                "a hosted database (Supabase/Neon PostgreSQL or MySQL) is required. "
                "Silent SQLite fallback is disabled to prevent data loss on ephemeral serverless filesystems."
            )

        return create_engine("sqlite://", creator=_cloud_db_unconfigured_creator)

    # 4. Local SQLite Default
    sqlite_url = DEFAULT_SQLITE_URL
    sqlite_engine = create_engine(
        sqlite_url,
        connect_args={"check_same_thread": False},
        echo=False,
    )
    _db_status = {
        "engine_name": "SQLite (Local)",
        "is_fallback": True if raw_url else False,
        "connected": True,
        "message": "Connected to local SQLite database." if not raw_url else "Hosted DB unreachable. Using local SQLite.",
        "url_masked": _mask_url(sqlite_url),
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
    """Return runtime connection health and engine identity for telemetry & Settings page."""
    return dict(_db_status)


def _migrate_sqlite_schema(eng: Engine) -> None:
    """Safely add missing columns to existing SQLite databases."""
    try:
        with eng.connect() as conn:
            # Check images columns
            res = conn.execute(text("PRAGMA table_info(images)"))
            existing_cols = {row[1] for row in res.fetchall()}
            if existing_cols:
                if "status" not in existing_cols:
                    conn.execute(text("ALTER TABLE images ADD COLUMN status VARCHAR(32) DEFAULT 'done'"))
                if "caption" not in existing_cols:
                    conn.execute(text("ALTER TABLE images ADD COLUMN caption TEXT"))

            # Check image_dna columns
            res = conn.execute(text("PRAGMA table_info(image_dna)"))
            dna_cols = {row[1] for row in res.fetchall()}
            if dna_cols:
                if "embedding_json" not in dna_cols:
                    conn.execute(text("ALTER TABLE image_dna ADD COLUMN embedding_json JSON"))
            conn.commit()
    except Exception as exc:
        logger.debug("SQLite schema migration check: %s", exc)


def init_db() -> None:
    """Initialize database tables idempotently with thread-safe guard."""
    global _tables_initialized
    if (IS_VERCEL or AI_MODE == "cloud") and not DB_URL and not (os.getenv("TESTING") == "1" or (DB_URL or "").startswith("sqlite:///:memory:")):
        raise RuntimeError(
            "Cloud mode database error: DB_URL is not set. In cloud/serverless mode, "
            "a hosted database (Supabase/Neon PostgreSQL or MySQL) is required. "
            "Silent SQLite fallback is disabled to prevent data loss on ephemeral serverless filesystems."
        )
    with _init_lock:
        if not _tables_initialized:
            try:
                Base.metadata.create_all(bind=engine)
                if "sqlite" in str(engine.url):
                    _migrate_sqlite_schema(engine)
                _tables_initialized = True
                logger.info("Database schema initialized successfully on %s", _db_status.get("engine_name", "database"))
            except Exception as exc:
                logger.error("Failed to initialize database tables: %s", exc)
                raise


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Context manager yielding a transactional database session."""
    if (IS_VERCEL or AI_MODE == "cloud") and not DB_URL and not (os.getenv("TESTING") == "1" or (DB_URL or "").startswith("sqlite:///:memory:")):
        raise RuntimeError(
            "Cloud mode database error: DB_URL is not set. In cloud/serverless mode, "
            "a hosted database (Supabase/Neon PostgreSQL or MySQL) is required. "
            "Silent SQLite fallback is disabled to prevent data loss on ephemeral serverless filesystems."
        )
    session: Session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.error("Transaction rolled back: %s", exc)
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for injecting transactional database sessions into routes."""
    if (IS_VERCEL or AI_MODE == "cloud") and not DB_URL and not (os.getenv("TESTING") == "1" or (DB_URL or "").startswith("sqlite:///:memory:")):
        raise RuntimeError(
            "Cloud mode database error: DB_URL is not set. In cloud/serverless mode, "
            "a hosted database (Supabase/Neon PostgreSQL or MySQL) is required. "
            "Silent SQLite fallback is disabled to prevent data loss on ephemeral serverless filesystems."
        )
    session: Session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
