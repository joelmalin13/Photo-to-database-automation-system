"""Analytics and statistics aggregation service for SnapBase.

Compiles real database counts for Chart.js:
- Category distribution (pie/donut)
- Monthly ingestion trends (line)
- Success vs failure ratios (bar)
- Receipt expenses & top shops by spend
- Student marks comparison & performance
"""

from __future__ import annotations

from typing import Any, Dict
from sqlalchemy.orm import Session

from db.crud import get_analytics_data, get_dashboard_metrics


class StatsService:
    """Aggregates operational metrics for dashboards and analytics endpoints."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Compile basic metrics for the home dashboard cards and charts."""
        analytics = get_analytics_data(self.db)
        metrics = analytics["metrics"]

        return {
            "has_data": metrics["total_documents"] > 0,
            "total_documents": metrics["total_documents"],
            "verified_count": metrics["verified_count"],
            "pending_review": metrics["pending_review"],
            "rejected_count": metrics["rejected_count"],
            "failed_count": metrics["failed_count"],
            "status_counts": metrics["status_counts"],
            "category_counts": metrics["category_counts"],
            "type_counts": metrics["type_counts"],
            "average_confidence": metrics["average_confidence"],
            "timeseries": {
                "labels": analytics["monthly_trend"]["labels"],
                "values": analytics["monthly_trend"]["values"],
                "counts": analytics["monthly_trend"]["values"],
            },
        }

    def get_full_analytics(self) -> Dict[str, Any]:
        """Compile complete analytics package for the dedicated Analytics page."""
        return get_analytics_data(self.db)
