"""SQLAlchemy 2.0 ORM database models for PixelMind.

Defines the normalized relational schema for images, YOLO detections,
Image DNA fingerprints, statistical anomalies, and processing audit logs.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.dialects.mysql import JSON as MySQLJSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 declarative base with generic JSON dialect fallback."""

    type_annotation_map = {
        dict: JSON().with_variant(MySQLJSON, "mysql"),
        list: JSON().with_variant(MySQLJSON, "mysql"),
    }


class Image(Base):
    """Primary visual intelligence entity representing an ingested photograph."""

    __tablename__ = "images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(500), nullable=False)
    annotated_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    phash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False, default="Uncategorized", index=True)
    scene: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    environment: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    detections: Mapped[List[Detection]] = relationship(
        "Detection", back_populates="image", cascade="all, delete-orphan", lazy="selectin"
    )
    dna: Mapped[Optional[ImageDNA]] = relationship(
        "ImageDNA", back_populates="image", cascade="all, delete-orphan", uselist=False, lazy="selectin"
    )
    anomaly: Mapped[Optional[Anomaly]] = relationship(
        "Anomaly", back_populates="image", cascade="all, delete-orphan", uselist=False, lazy="selectin"
    )
    logs: Mapped[List[ProcessingLog]] = relationship(
        "ProcessingLog", back_populates="image", cascade="all, delete-orphan", lazy="selectin"
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert image entity to dictionary representation."""
        return {
            "id": self.id,
            "filename": self.filename,
            "stored_path": self.stored_path,
            "annotated_path": self.annotated_path,
            "sha256": self.sha256,
            "phash": self.phash,
            "width": self.width,
            "height": self.height,
            "category": self.category,
            "scene": self.scene,
            "environment": self.environment,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "detections_count": sum(d.count for d in self.detections) if self.detections else 0,
            "labels": [d.label for d in self.detections] if self.detections else [],
            "has_anomaly": self.anomaly is not None,
        }


class Detection(Base):
    """Individual object class detected in an image by YOLO."""

    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    image_id: Mapped[int] = mapped_column(Integer, ForeignKey("images.id", ondelete="CASCADE"), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    avg_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_json: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    image: Mapped[Image] = relationship("Image", back_populates="detections")

    def to_dict(self) -> Dict[str, Any]:
        """Convert detection record to dictionary."""
        return {
            "id": self.id,
            "image_id": self.image_id,
            "label": self.label,
            "category": self.category,
            "count": self.count,
            "avg_confidence": round(self.avg_confidence, 3),
            "bboxes": self.bbox_json or [],
        }


class ImageDNA(Base):
    """Visual fingerprint storing dominant colors, composition summary, and CLIP embedding."""

    __tablename__ = "image_dna"

    image_id: Mapped[int] = mapped_column(Integer, ForeignKey("images.id", ondelete="CASCADE"), primary_key=True)
    dominant_colors_json: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    embedding_blob: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    composition_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    image: Mapped[Image] = relationship("Image", back_populates="dna")

    def to_dict(self) -> Dict[str, Any]:
        """Convert DNA record to dictionary representation."""
        return {
            "image_id": self.image_id,
            "dominant_colors": self.dominant_colors_json or [],
            "composition": self.composition_json or {},
            "has_embedding": self.embedding_blob is not None,
        }


class Anomaly(Base):
    """Statistical outlier alert indicating unusual object combinations or counts."""

    __tablename__ = "anomalies"

    image_id: Mapped[int] = mapped_column(Integer, ForeignKey("images.id", ondelete="CASCADE"), primary_key=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    image: Mapped[Image] = relationship("Image", back_populates="anomaly")

    def to_dict(self) -> Dict[str, Any]:
        """Convert anomaly flag to dictionary."""
        return {
            "image_id": self.image_id,
            "reason": self.reason,
            "score": round(self.score, 2),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ProcessingLog(Base):
    """Audit log recording ingestion and processing steps."""

    __tablename__ = "processing_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    image_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("images.id", ondelete="CASCADE"), nullable=True, index=True)
    step: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_time_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    image: Mapped[Optional[Image]] = relationship("Image", back_populates="logs")
