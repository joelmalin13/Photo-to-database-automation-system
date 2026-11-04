"""Comprehensive reporting and export service using OpenPyXL and Pandas.

Generates:
- Formatted Excel workbooks (.xlsx) with styled header rows, auto column widths,
  formatted currencies, and an Executive Summary sheet.
- Clean CSV data streams.
- Structured text summary reports for operational review.
"""

from __future__ import annotations

from datetime import datetime, timezone
import io
import json
from typing import Any, Dict, List, Optional, Tuple
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
import pandas as pd
from sqlalchemy.orm import Session

from config.settings import logger
from db.crud import list_documents


class ReportService:
    """Handles report generation and formatted multi-sheet export workflows."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def generate_report(
        self,
        export_format: str = "xlsx",
        category: Optional[str] = None,
        status: Optional[str] = None,
        search_query: Optional[str] = None,
    ) -> Tuple[bytes, str, str]:
        """Generate filtered document dataset in the specified export format."""
        docs, total = list_documents(
            session=self.db,
            category=category,
            status=status,
            search_query=search_query,
            page=1,
            page_size=1000,
        )

        flat_rows: List[Dict[str, Any]] = []
        for d in docs:
            d_dict = d.to_dict()
            row = {
                "Document ID": d_dict["id"],
                "Filename": d_dict["filename"],
                "Category": d_dict["category"],
                "Status": d_dict["status"],
                "OCR Confidence": f"{d_dict['ocr_confidence'] * 100:.1f}%",
                "Created At": d_dict["created_at"][:19].replace("T", " ")
                if d_dict["created_at"]
                else "",
            }

            # If confirmed record exists, pull verified fields
            confirmed = d_dict.get("confirmed_data")
            if confirmed:
                for ck, cv in confirmed.items():
                    if ck not in ("id", "document_id", "items", "marks", "created_at"):
                        row[f"Verified {ck.replace('_', ' ').title()}"] = cv
            else:
                # Fall back to raw extracted fields
                for rk, rv in d_dict.get("fields", {}).items():
                    row[f"Extracted {rk.replace('_', ' ').title()}"] = rv

            flat_rows.append(row)

        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        if export_format == "xlsx":
            content = self._build_styled_excel(flat_rows, category or "All", total)
            filename = f"snapbase_report_{timestamp_str}.xlsx"
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            return content, media_type, filename

        elif export_format == "csv":
            df = pd.DataFrame(flat_rows)
            csv_str = df.to_csv(index=False)
            filename = f"snapbase_export_{timestamp_str}.csv"
            media_type = "text/csv"
            return csv_str.encode("utf-8"), media_type, filename

        elif export_format == "json":
            df_records = [d.to_dict() for d in docs]
            json_str = json.dumps(df_records, indent=2, default=str)
            filename = f"snapbase_export_{timestamp_str}.json"
            media_type = "application/json"
            return json_str.encode("utf-8"), media_type, filename

        # Summary text report
        summary_txt = self._build_summary_text(flat_rows, total)
        filename = f"snapbase_summary_{timestamp_str}.txt"
        media_type = "text/plain"
        return summary_txt.encode("utf-8"), media_type, filename

    def _build_styled_excel(
        self, rows: List[Dict[str, Any]], category_label: str, total_count: int
    ) -> bytes:
        """Construct a multi-sheet formatted workbook using openpyxl."""
        wb = openpyxl.Workbook()

        # Sheet 1: Records Table
        ws_records = wb.active
        ws_records.title = "Documents Repository"
        ws_records.views.sheetView[0].showGridLines = True

        # Styles
        header_fill = PatternFill(start_color="111827", end_color="111827", fill_type="solid")
        header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        regular_font = Font(name="Segoe UI", size=10)
        border_thin = Side(border_style="thin", color="E5E7EB")
        cell_border = Border(left=border_thin, right=border_thin, top=border_thin, bottom=border_thin)

        if rows:
            headers = list(rows[0].keys())
            ws_records.append(headers)

            # Style header row
            for col_num in range(1, len(headers) + 1):
                cell = ws_records.cell(row=1, column=col_num)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

            # Append data rows
            for r_idx, row_dict in enumerate(rows, start=2):
                row_vals = [row_dict.get(h, "") for h in headers]
                ws_records.append(row_vals)
                for col_num in range(1, len(headers) + 1):
                    c = ws_records.cell(row=r_idx, column=col_num)
                    c.font = regular_font
                    c.border = cell_border
                    if isinstance(c.value, (int, float)):
                        c.alignment = Alignment(horizontal="right")
                    else:
                        c.alignment = Alignment(horizontal="left")

            # Auto-fit column widths
            for col in ws_records.columns:
                max_len = max(len(str(cell.value or "")) for cell in col)
                col_letter = get_column_letter(col[0].column)
                ws_records.column_dimensions[col_letter].width = max(max_len + 4, 12)

        else:
            ws_records.append(["No records available for the requested filters."])

        # Sheet 2: Executive Summary
        ws_summary = wb.create_sheet(title="Executive Summary")
        ws_summary.views.sheetView[0].showGridLines = True

        title_font = Font(name="Segoe UI", size=14, bold=True, color="C62828")
        bold_font = Font(name="Segoe UI", size=11, bold=True)

        ws_summary.append(["SnapBase Operational Summary Report"])
        ws_summary.cell(row=1, column=1).font = title_font
        ws_summary.append([])

        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        summary_rows = [
            ("Report Generation Date", now_utc),
            ("Filtered Category", category_label.title()),
            ("Total Records Exported", total_count),
        ]
        for label, val in summary_rows:
            ws_summary.append([label, val])
            ws_summary.cell(row=ws_summary.max_row, column=1).font = bold_font

        ws_summary.column_dimensions["A"].width = 28
        ws_summary.column_dimensions["B"].width = 35

        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    def _build_summary_text(self, rows: List[Dict[str, Any]], total: int) -> str:
        """Build text summary report."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        lines = [
            "=" * 60,
            "SNAPBASE AUTOMATION PLATFORM: EXECUTIVE SUMMARY REPORT",
            "=" * 60,
            f"Generated: {now}",
            f"Total Document Records Exported: {total}",
            "-" * 60,
        ]
        if rows:
            for idx, r in enumerate(rows[:20], 1):
                lines.append(f"{idx:02d}. #{r.get('Document ID')} | {r.get('Filename')} | {r.get('Category')} | {r.get('Status')} | Conf: {r.get('OCR Confidence')}")
            if total > 20:
                lines.append(f"... and {total - 20} more records.")
        else:
            lines.append("No documents matched the query.")
        lines.append("=" * 60)
        return "\n".join(lines)
