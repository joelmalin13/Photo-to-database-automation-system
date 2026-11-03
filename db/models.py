"""SQLAlchemy 2.0 models for SnapBase documents, fields, and line items.

Defines typed schema for captured document records, individual extracted
attributes, confidence scores, and tabular line items.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from config.settings import DocumentStatus


def utc_now() -> datetime:
    """Return current UTC timestamp without timezone offset for SQLite compatibility."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    """Declarative base class for SnapBase entity models."""


class Document(Base):
    """Database entity representing an ingested document photograph."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    image_path: Mapped[str] = mapped_column(String(500), nullable=False)
    image_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=DocumentStatus.PENDING.value,
        index=True,
    )
    is_edited: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    # Relationships
    fields: Mapped[List[DocumentField]] = relationship(
        "DocumentField",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentField.id",
    )
    line_items: Mapped[List[LineItem]] = relationship(
        "LineItem",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="LineItem.item_index",
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert the document model and its associated fields to a dictionary.

        Returns:
            Dict[str, Any]: Serialized document record.
        """
        return {
            "id": self.id,
            "type": self.type,
            "filename": self.filename,
            "image_path": self.image_path,
            "image_hash": self.image_hash,
            "status": self.status,
            "is_edited": self.is_edited,
            "created_at": (
                self.created_at.isoformat() if self.created_at else None
            ),
            "updated_at": (
                self.updated_at.isoformat() if self.updated_at else None
            ),
            "fields": {f.key: f.value for f in self.fields},
            "field_confidences": {f.key: f.confidence for f in self.fields},
            "line_items": [li.to_dict() for li in self.line_items],
        }


class DocumentField(Base):
    """Database entity representing a single structured field extracted from a document."""

    __tablename__ = "fields"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    is_edited: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationship
    document: Mapped[Document] = relationship("Document", back_populates="fields")

    def to_dict(self) -> Dict[str, Any]:
        """Convert field entity to dictionary."""
        return {
            "id": self.id,
            "document_id": self.document_id,
            "key": self.key,
            "value": self.value,
            "confidence": self.confidence,
            "is_edited": self.is_edited,
        }


class LineItem(Base):
    """Database entity representing repeated tabular rows (e.g. invoice items)."""

    __tablename__ = "line_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    data_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    # Relationship
    document: Mapped[Document] = relationship("Document", back_populates="line_items")

    def to_dict(self) -> Dict[str, Any]:
        """Convert line item entity to dictionary."""
        try:
            parsed = json.loads(self.data_json)
        except Exception:
            parsed = {}
        parsed["id"] = self.id
        parsed["item_index"] = self.item_index
        return parsed
