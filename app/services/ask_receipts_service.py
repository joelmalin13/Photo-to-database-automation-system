"""Ask Your Receipts natural language query service (Slide 6 #6).

Supports conversational queries such as:
- 'total spent at ABC MART in November'
- 'how much did I spend on groceries?'
- 'what was my highest expense?'
- 'show receipts above 1000'
- 'how many receipts were uploaded?'
Works 100% offline using SQLite aggregation & regex rules, with optional Gemini enhancement.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from sqlalchemy import func, select, desc
from sqlalchemy.orm import Session

from config.settings import GEMINI_API_KEY, GEMINI_MODEL, logger
from db.models import Document, Receipt


MONTH_MAP = {
    "january": "01", "jan": "01",
    "february": "02", "feb": "02",
    "march": "03", "mar": "03",
    "april": "04", "apr": "04",
    "may": "05",
    "june": "06", "jun": "06",
    "july": "07", "jul": "07",
    "august": "08", "aug": "08",
    "september": "09", "sep": "09", "sept": "09",
    "october": "10", "oct": "10",
    "november": "11", "nov": "11",
    "december": "12", "dec": "12",
}


class AskReceiptsService:
    """Answers natural language questions about saved receipts from the database."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def query(self, question: str) -> Dict[str, Any]:
        """Process natural language question and return structured answer and matching records."""
        q = question.strip()
        q_lower = q.lower()

        # 1. Check for Highest / Maximum expense
        if any(w in q_lower for w in ["highest", "maximum", "max", "most expensive", "biggest"]):
            return self._handle_highest_expense()

        # 2. Check for Count of receipts
        if any(w in q_lower for w in ["how many", "count of", "number of receipts", "total receipts"]):
            return self._handle_receipt_count()

        # 3. Check for receipts above / over / greater than a threshold
        above_match = re.search(r"(?:above|over|greater than|more than)[^0-9]*([0-9]+(?:[.,][0-9]{1,2})?)", q_lower)
        if above_match:
            try:
                min_amt = float(above_match.group(1).replace(",", ""))
                return self._handle_receipts_above(min_amt)
            except ValueError:
                pass

        # 4. Check for Average spend
        if any(w in q_lower for w in ["average", "avg", "mean spend"]):
            return self._handle_average_spend()

        # 5. Check for Category queries (Groceries, Restaurant, Stationery, etc.)
        for cat in ["grocery", "groceries", "restaurant", "food", "stationery", "pharmacy", "electronics", "clothing"]:
            if cat in q_lower:
                return self._handle_category_spend(cat)

        # 6. Combined Shop + Month (e.g. 'total spent at ABC MART in November')
        month_found = None
        for m_name, m_num in MONTH_MAP.items():
            if re.search(rf"\b{m_name}\b", q_lower):
                month_found = (m_name.capitalize(), m_num)
                break

        shop_match = re.search(r"(?:at|from|in)\s+([A-Za-z0-9&'\s]+?)(?:\s+in|\s+during|\s+for|\?|$)", q, re.IGNORECASE)
        shop_query = None
        if shop_match:
            candidate = shop_match.group(1).strip()
            # Ignore month if matched as shop
            if candidate.lower() not in MONTH_MAP:
                shop_query = candidate

        if shop_query or month_found:
            return self._handle_shop_and_month(shop_query, month_found)

        # 7. Check for Total overall spend
        if any(w in q_lower for w in ["total spent", "total spend", "how much did i spend", "total expenses", "how much spent"]):
            return self._handle_total_spend()

        # 8. Fallback: Search receipts matching query words
        return self._handle_fallback_search(q)

    def _handle_highest_expense(self) -> Dict[str, Any]:
        """Find the receipt with the largest total amount."""
        receipt = self.db.scalar(
            select(Receipt).order_by(desc(Receipt.total_amount)).limit(1)
        )
        if not receipt:
            return {
                "answer": "No confirmed receipts found in the database yet.",
                "total": 0.0,
                "count": 0,
                "receipts": [],
            }
        date_str = receipt.date.strftime("%Y-%m-%d") if receipt.date else "Unknown Date"
        return {
            "answer": f"Your highest expense was ₹{receipt.total_amount:,.2f} at {receipt.shop_name} on {date_str}.",
            "total": receipt.total_amount,
            "count": 1,
            "receipts": [receipt.to_dict()],
        }

    def _handle_receipt_count(self) -> Dict[str, Any]:
        """Count verified and pending receipts in the system."""
        confirmed_count = self.db.scalar(select(func.count(Receipt.id))) or 0
        total_docs = self.db.scalar(select(func.count(Document.id))) or 0
        return {
            "answer": f"You have {confirmed_count} confirmed receipt(s) in the database ({total_docs} total document(s) uploaded).",
            "count": confirmed_count,
            "receipts": [],
        }

    def _handle_receipts_above(self, min_amt: float) -> Dict[str, Any]:
        """Find all receipts with total_amount >= min_amt."""
        receipts = list(
            self.db.scalars(
                select(Receipt)
                .where(Receipt.total_amount >= min_amt)
                .order_by(desc(Receipt.total_amount))
            )
        )
        if not receipts:
            return {
                "answer": f"No receipts found with total amount above ₹{min_amt:,.2f}.",
                "total": 0.0,
                "count": 0,
                "receipts": [],
            }
        sum_amt = sum(r.total_amount for r in receipts)
        names = ", ".join(f"{r.shop_name} (₹{r.total_amount:,.2f})" for r in receipts[:3])
        if len(receipts) > 3:
            names += f" and {len(receipts) - 3} more"
        return {
            "answer": f"Found {len(receipts)} receipt(s) above ₹{min_amt:,.2f} totaling ₹{sum_amt:,.2f}: {names}.",
            "total": round(sum_amt, 2),
            "count": len(receipts),
            "receipts": [r.to_dict() for r in receipts],
        }

    def _handle_average_spend(self) -> Dict[str, Any]:
        """Calculate average receipt spend."""
        avg_val = self.db.scalar(select(func.avg(Receipt.total_amount)))
        count = self.db.scalar(select(func.count(Receipt.id))) or 0
        if not avg_val or count == 0:
            return {
                "answer": "No receipts recorded yet to compute average.",
                "total": 0.0,
                "count": 0,
                "receipts": [],
            }
        return {
            "answer": f"Your average spend per receipt is ₹{avg_val:,.2f} across {count} confirmed receipt(s).",
            "total": round(float(avg_val), 2),
            "count": count,
            "receipts": [],
        }

    def _handle_category_spend(self, cat_term: str) -> Dict[str, Any]:
        """Calculate total spend for a given category."""
        target_cat = "Grocery" if "groc" in cat_term else cat_term.capitalize()
        receipts = list(
            self.db.scalars(
                select(Receipt)
                .where(Receipt.category.ilike(f"%{target_cat}%"))
                .order_by(desc(Receipt.total_amount))
            )
        )
        if not receipts:
            return {
                "answer": f"No receipts recorded under category '{target_cat}'.",
                "total": 0.0,
                "count": 0,
                "receipts": [],
            }
        sum_amt = sum(r.total_amount for r in receipts)
        return {
            "answer": f"You spent a total of ₹{sum_amt:,.2f} on {target_cat} across {len(receipts)} receipt(s).",
            "total": round(sum_amt, 2),
            "count": len(receipts),
            "receipts": [r.to_dict() for r in receipts],
        }

    def _handle_shop_and_month(
        self, shop_name: Optional[str], month_info: Optional[tuple[str, str]]
    ) -> Dict[str, Any]:
        """Handle 'total spent at [SHOP] in [MONTH]'."""
        stmt = select(Receipt)
        desc_parts = []

        if shop_name:
            stmt = stmt.where(Receipt.shop_name.ilike(f"%{shop_name}%"))
            desc_parts.append(f"at {shop_name}")

        if month_info:
            m_name, m_num = month_info
            # Match date format YYYY-MM-DD (e.g. %-11-%)
            stmt = stmt.where(func.strftime("%m", Receipt.date) == m_num)
            desc_parts.append(f"in {m_name}")

        receipts = list(self.db.scalars(stmt.order_by(desc(Receipt.total_amount))))
        if not receipts:
            # Also check documents if not yet confirmed
            doc_stmt = select(Document).where(Document.category == "receipts")
            if shop_name:
                doc_stmt = doc_stmt.where(Document.ocr_text.ilike(f"%{shop_name}%"))
            doc_items = list(self.db.scalars(doc_stmt))
            if doc_items:
                tot = sum(
                    float(d.raw_fields_json.get("fields", {}).get("total_amount") or 0.0)
                    for d in doc_items if d.raw_fields_json
                )
                label = " ".join(desc_parts)
                return {
                    "answer": f"Found {len(doc_items)} receipt(s) {label} totaling ₹{tot:,.2f} (pending verification).",
                    "total": round(tot, 2),
                    "count": len(doc_items),
                    "receipts": [d.to_dict() for d in doc_items],
                }

            label = " ".join(desc_parts)
            return {
                "answer": f"No receipts found {label}.",
                "total": 0.0,
                "count": 0,
                "receipts": [],
            }

        sum_amt = sum(r.total_amount for r in receipts)
        label = " ".join(desc_parts)
        return {
            "answer": f"Total spent {label}: ₹{sum_amt:,.2f} across {len(receipts)} receipt(s).",
            "total": round(sum_amt, 2),
            "count": len(receipts),
            "receipts": [r.to_dict() for r in receipts],
        }

    def _handle_total_spend(self) -> Dict[str, Any]:
        """Calculate total spend across all receipts."""
        total = self.db.scalar(select(func.sum(Receipt.total_amount))) or 0.0
        count = self.db.scalar(select(func.count(Receipt.id))) or 0
        return {
            "answer": f"Your total confirmed spending is ₹{total:,.2f} across {count} receipt(s).",
            "total": round(float(total), 2),
            "count": count,
            "receipts": [],
        }

    def _handle_fallback_search(self, q: str) -> Dict[str, Any]:
        """Perform generic search across receipts and documents."""
        receipts = list(
            self.db.scalars(
                select(Receipt)
                .where(
                    Receipt.shop_name.ilike(f"%{q}%")
                    | Receipt.category.ilike(f"%{q}%")
                    | Receipt.raw_text.ilike(f"%{q}%")
                )
                .limit(5)
            )
        )
        if receipts:
            sum_amt = sum(r.total_amount for r in receipts)
            return {
                "answer": f"Found {len(receipts)} matching receipt(s) totaling ₹{sum_amt:,.2f}.",
                "total": round(sum_amt, 2),
                "count": len(receipts),
                "receipts": [r.to_dict() for r in receipts],
            }

        return {
            "answer": f"I couldn't find any receipts matching '{q}'. Try asking: 'Total spent at ABC MART in November' or 'How much did I spend on Groceries?'",
            "total": 0.0,
            "count": 0,
            "receipts": [],
        }
