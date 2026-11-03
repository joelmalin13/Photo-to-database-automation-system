"""FastAPI dependencies for request-scoped database sessions and services.

Provides session lifecycle management with automatic rollback on error.
"""

from __future__ import annotations

from typing import Generator
from fastapi import Depends
from sqlalchemy.orm import Session

from db.session import SessionFactory


def get_db() -> Generator[Session, None, None]:
    """Provide a transactional database session dependency for API requests.

    Yields:
        Session: Active SQLAlchemy session.
    """
    session: Session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
