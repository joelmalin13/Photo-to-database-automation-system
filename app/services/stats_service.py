"""Analytics and statistics aggregation service for SnapBase.

Calculates KPI metrics, status distributions, accuracy ratios, time-series
ingestion volumes, and recent activity logs.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List
from sqlalchemy import func
from sqlalchemy.orm import Session

from config.settings import DocumentStatus
from db.crud import get_dashboard_metrics, list_documents
from db.models import Document, DocumentField


class StatsService:
    """Aggregates operational metrics for dashboards and analytics endpoints."""

    def __init__(self, db: Session) -> None:
        """Initialize stats service with database session."""
        self.db = db

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Compile complete analytics package for dashboard metrics and charts."""
        base_metrics = get_dashboard_metrics(self.db)
        total_docs = base_metrics["total_documents"]

        # Time-series ingestion volume for Line Chart
        dates_query = (
            self.db.query(
                func.date(Document.created_at).label("day"),
                func.count(Document.id),
            )
            .group_by("day")
            .order_by("day")
            .all()
        )
        timeseries_labels = [row[0] for row in dates_query]
        timeseries_values = [row[1] for row in dates_query]

        # Recent activity stream
        recent_docs, _ = list_documents(
            self.db, page=1, page_size=6, sort_by="created_at", sort_order="desc"
        )
        recent_activity: List[Dict[str, Any]] = [
            {
                "id": d.id,
                "filename": d.filename,
                "type": d.type,
                "status": d.status,
                "is_edited": d.is_edited,
                "created_at": d.created_at.strftime("%Y-%m-%d %H:%M")
                if d.created_at
                else "",
            }
            for d in recent_docs
        ]

        return {
            "has_data": total_docs > 0,
            "total_documents": total_docs,
            "status_counts": base_metrics["status_counts"],
            "type_counts": base_metrics["type_counts"],
            "edited_count": base_metrics["edited_count"],
            "unedited_count": base_metrics["unedited_count"],
            "accuracy_rate": base_metrics["accuracy_rate"],
            "average_confidence": base_metrics["average_confidence"],
            "timeseries": {
                "labels": timeseries_labels,
                "values": timeseries_values,
                "counts": timeseries_values,
            },
            "recent_activity": recent_activity,
        }
