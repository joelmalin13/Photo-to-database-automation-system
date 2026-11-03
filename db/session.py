"""Database engine setup, initialization, and session context manager.

Provides transactional session management with automatic commit and rollback.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from config.settings import DATABASE_URL, logger
from db.models import Base

# Engine configuration for SQLite thread safety
engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False}
    if DATABASE_URL.startswith("sqlite")
    else {},
)

SessionFactory = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def init_db() -> None:
    """Initialize database tables idempotently at startup."""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized successfully at %s", DATABASE_URL)
    except Exception as exc:
        logger.error("Failed to initialize database: %s", exc)
        raise


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Provide a transactional database session context manager.

    Yields:
        Session: Active SQLAlchemy session.

    Raises:
        Exception: Re-raises any exception after triggering a rollback.
    """
    session: Session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.error("Transaction rolled back due to error: %s", exc)
        raise
    finally:
        session.close()
