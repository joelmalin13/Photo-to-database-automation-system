"""Visual intelligence analytics and statistical metrics service for PixelMind.

Compiles dataset aggregations for Chart.js:
- Total images, total detected objects, anomaly counts
- Most frequent object classes (horizontal bar chart)
- Category distribution (pie/donut chart)
- Scene & environment distribution (bar chart)
- Monthly ingestion trends (line chart)
"""

from __future__ import annotations

from typing import Any, Dict
from sqlalchemy.orm import Session
from db.crud import get_analytics_summary


class AnalyticsService:
    """Service providing aggregated visual intelligence metrics."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_dashboard_metrics(self) -> Dict[str, Any]:
        """Aggregate summary metrics and Chart.js datasets with empty-state protection."""
        summary = get_analytics_summary(self.db)
        return summary
