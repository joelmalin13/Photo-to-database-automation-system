"""Data export service for CSV, Excel (.xlsx), and JSON representations.

Serializes filtered document records with flattened fields for external reporting.
"""

from __future__ import annotations

import io
import json
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
from sqlalchemy.orm import Session

from db.crud import list_documents


class ExportService:
    """Handles serialization and formatting of document datasets."""

    def __init__(self, db: Session) -> None:
        """Initialize export service with database session."""
        self.db = db

    def generate_export_dataframe(
        self,
        doc_type: Optional[str] = None,
        status: Optional[str] = None,
        search_query: Optional[str] = None,
    ) -> pd.DataFrame:
        """Retrieve and flatten document records into a structured DataFrame."""
        items, _ = list_documents(
            session=self.db,
            doc_type=doc_type if doc_type != "all" else None,
            status=status if status != "all" else None,
            search_query=search_query,
            page=1,
            page_size=100000,
        )

        rows: List[Dict[str, Any]] = []
        for doc in items:
            row: Dict[str, Any] = {
                "id": doc.id,
                "filename": doc.filename,
                "type": doc.type,
                "status": doc.status,
                "is_edited": doc.is_edited,
                "created_at": doc.created_at.isoformat() if doc.created_at else "",
                "updated_at": doc.updated_at.isoformat() if doc.updated_at else "",
            }
            for f in doc.fields:
                row[f"field_{f.key}"] = f.value
            rows.append(row)

        return pd.DataFrame(rows)

    def export(
        self,
        export_format: str,
        doc_type: Optional[str] = None,
        status: Optional[str] = None,
        search_query: Optional[str] = None,
    ) -> Tuple[bytes, str, str]:
        """Generate exported payload bytes, media type, and suggested filename.

        Args:
            export_format: 'csv', 'xlsx', or 'json'.
            doc_type: Document classification filter.
            status: Document review status filter.
            search_query: Search term filter.

        Returns:
            Tuple[bytes, str, str]: (payload_bytes, mime_type, filename)
        """
        df = self.generate_export_dataframe(doc_type, status, search_query)
        fmt = export_format.lower()

        if fmt == "xlsx":
            buffer = io.BytesIO()
            df.to_excel(buffer, index=False, engine="openpyxl")
            return (
                buffer.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "snapbase_export.xlsx",
            )

        if fmt == "json":
            json_str = df.to_json(orient="records", indent=2)
            return (
                json_str.encode("utf-8"),
                "application/json",
                "snapbase_export.json",
            )

        # Default CSV
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        return csv_bytes, "text/csv", "snapbase_export.csv"
