"""SQLAlchemy 2.0 ORM models for SnapBase.

Defines the normalized database schema:
- User
- Document (Master table holding raw extraction & OCR confidence)
- Receipt & ReceiptItem (Confirmed receipt data)
- Student & Mark (Confirmed academic marksheet data)
- BusinessCard (Confirmed contact card data)
- ProcessingHistory (Audit log of every pipeline operation)
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from config.settings import DocumentCategory, DocumentStatus


def utc_now() -> datetime:
    """Provide current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Declarative base class for all SnapBase database entities."""
    pass


class User(Base):
    """System user or operator entity."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    documents: Mapped[List[Document]] = relationship("Document", back_populates="user")


class Document(Base):
    """Master document entity storing raw OCR results, confidence, and status."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    image_path: Mapped[str] = mapped_column(String(500), nullable=False)
    image_hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(
        String(50), nullable=False, default=DocumentCategory.RECEIPTS.value, index=True
    )
    ocr_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ocr_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=DocumentStatus.PROCESSED.value,
        index=True,
    )
    raw_fields_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    user: Mapped[Optional[User]] = relationship("User", back_populates="documents")
    receipt: Mapped[Optional[Receipt]] = relationship(
        "Receipt", back_populates="document", uselist=False, cascade="all, delete-orphan"
    )
    student: Mapped[Optional[Student]] = relationship(
        "Student", back_populates="document", uselist=False, cascade="all, delete-orphan"
    )
    business_card: Mapped[Optional[BusinessCard]] = relationship(
        "BusinessCard", back_populates="document", uselist=False, cascade="all, delete-orphan"
    )
    history: Mapped[List[ProcessingHistory]] = relationship(
        "ProcessingHistory",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="ProcessingHistory.id.desc()",
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize document and its extracted or confirmed data."""
        raw_data = self.raw_fields_json or {}
        # Backwards compatible alias properties
        extracted_fields = raw_data.get("fields", {}) if isinstance(raw_data, dict) else {}
        confidences = raw_data.get("confidences", {}) if isinstance(raw_data, dict) else {}
        line_items = raw_data.get("line_items", []) if isinstance(raw_data, dict) else []

        confirmed = None
        if self.receipt:
            confirmed = self.receipt.to_dict()
        elif self.student:
            confirmed = self.student.to_dict()
        elif self.business_card:
            confirmed = self.business_card.to_dict()

        return {
            "id": self.id,
            "filename": self.filename,
            "image_path": self.image_path,
            "image_hash": self.image_hash,
            "category": self.category,
            "type": self.category,  # Compatibility alias
            "status": self.status,
            "ocr_text": self.ocr_text,
            "ocr_confidence": round(float(self.ocr_confidence), 4),
            "confidence": round(float(self.ocr_confidence), 2),  # Compatibility alias
            "fields": extracted_fields,
            "field_confidences": confidences,
            "line_items": line_items,
            "confirmed_data": confirmed,
            "is_verified": self.status == DocumentStatus.VERIFIED.value,
            "engine_used": raw_data.get("engine_used", "EasyOCR") if isinstance(raw_data, dict) else "EasyOCR",
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Receipt(Base):
    """Confirmed commercial receipt or invoice record matching Slide 5."""

    __tablename__ = "receipts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), unique=True, nullable=True
    )
    shop_name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    date: Mapped[Optional[datetime.date]] = mapped_column(Date, nullable=True, index=True)
    total_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    pincode: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    category: Mapped[str] = mapped_column(String(50), default="Grocery", nullable=False, index=True)
    ocr_confidence: Mapped[float] = mapped_column(Float, default=0.85, nullable=False)
    image_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_verified: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    image_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    receipt_number: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    subtotal: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    tax_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    # Relationships
    document: Mapped[Optional[Document]] = relationship("Document", back_populates="receipt")
    items: Mapped[List[ReceiptItem]] = relationship(
        "ReceiptItem", back_populates="receipt", cascade="all, delete-orphan"
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert receipt to dictionary matching Slide 5."""
        return {
            "id": self.id,
            "document_id": self.document_id,
            "shop_name": self.shop_name,
            "date": self.date.isoformat() if self.date else None,
            "total_amount": self.total_amount,
            "phone": self.phone,
            "email": self.email,
            "pincode": self.pincode,
            "category": self.category,
            "ocr_confidence": round(float(self.ocr_confidence), 4),
            "image_path": self.image_path,
            "raw_text": self.raw_text,
            "is_verified": self.is_verified,
            "image_hash": self.image_hash,
            "receipt_number": self.receipt_number,
            "subtotal": self.subtotal,
            "tax_amount": self.tax_amount,
            "items": [it.to_dict() for it in self.items],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ReceiptItem(Base):
    """Line item within a confirmed receipt."""

    __tablename__ = "receipt_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    receipt_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("receipts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_name: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    receipt: Mapped[Receipt] = relationship("Receipt", back_populates="items")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "item_name": self.item_name,
            "quantity": self.quantity,
            "unit_price": self.unit_price,
            "total_price": self.total_price,
        }


class Student(Base):
    """Confirmed student marksheet record."""

    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    usn: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    college: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, index=True)
    semester: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    total_marks: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    percentage: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    result: Mapped[str] = mapped_column(String(30), default="PASS", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    # Relationships
    document: Mapped[Document] = relationship("Document", back_populates="student")
    marks: Mapped[List[Mark]] = relationship(
        "Mark", back_populates="student", cascade="all, delete-orphan"
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "name": self.name,
            "usn": self.usn,
            "college": self.college,
            "semester": self.semester,
            "total_marks": self.total_marks,
            "percentage": self.percentage,
            "result": self.result,
            "marks": [m.to_dict() for m in self.marks],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Mark(Base):
    """Subject score within a student marksheet."""

    __tablename__ = "marks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject_name: Mapped[str] = mapped_column(String(150), nullable=False)
    subject_code: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    marks_obtained: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    max_marks: Mapped[float] = mapped_column(Float, default=100.0, nullable=False)

    student: Mapped[Student] = relationship("Student", back_populates="marks")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "subject_name": self.subject_name,
            "subject_code": self.subject_code,
            "marks_obtained": self.marks_obtained,
            "max_marks": self.max_marks,
        }


class BusinessCard(Base):
    """Confirmed visiting card contact details."""

    __tablename__ = "business_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    person_name: Mapped[str] = mapped_column(String(120), nullable=False)
    designation: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    company_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    website: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    document: Mapped[Document] = relationship("Document", back_populates="business_card")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "person_name": self.person_name,
            "designation": self.designation,
            "company_name": self.company_name,
            "phone": self.phone,
            "email": self.email,
            "website": self.website,
            "address": self.address,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ProcessingHistory(Base):
    """Log entry recording each step and error during document processing."""

    __tablename__ = "processing_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_name: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="success", nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_time_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False, index=True)

    document: Mapped[Document] = relationship("Document", back_populates="history")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "step_name": self.step_name,
            "status": self.status,
            "details": self.details,
            "execution_time_ms": self.execution_time_ms,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
