"""Natural language search and conversational visual intelligence service for PixelMind.

Implements:
1. Natural language image retrieval using CLIP text-to-image latent similarity
   combined with lexical object matching.
2. "Ask Your Images" rule-based query parser and Q&A engine.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List
import numpy as np
from sqlalchemy.orm import Session

from core.embedder import ClipEmbedder
from core.query_parser import QueryResult, parse_and_execute_query
from db.crud import get_all_embeddings, get_image_by_id


class SearchService:
    """Service providing semantic visual search and natural language database querying."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.embedder = ClipEmbedder.get_instance()

    def natural_language_search(
        self,
        query: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Rank images using multimodal CLIP similarity combined with detected object boosts."""
        clean_query = query.strip()
        if not clean_query:
            return []

        # 1. Embed query sentence
        query_vec = self.embedder.embed_text(clean_query)
        stored_embeddings = get_all_embeddings(self.db)

        if not stored_embeddings:
            return []

        # 2. Extract query keywords for lexical boosting
        query_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", clean_query.lower()))

        scored_results: List[Tuple[int, float, List[str]]] = []

        for img_id, img_vec in stored_embeddings:
            cos_sim = self.embedder.compute_similarity(query_vec, img_vec)

            # Retrieve image to check object overlap
            img = get_image_by_id(self.db, img_id)
            if not img:
                continue

            matched_labels: List[str] = []
            if img.detections:
                for d in img.detections:
                    if d.label.lower() in query_words or any(w in d.label.lower() for w in query_words):
                        matched_labels.append(d.label)

            # Boost similarity if explicit objects match the query words
            boost = min(0.25, len(matched_labels) * 0.08)
            final_score = min(1.0, cos_sim + boost)

            scored_results.append((img_id, final_score, matched_labels))

        # Sort by similarity descending
        scored_results.sort(key=lambda x: x[1], reverse=True)

        output: List[Dict[str, Any]] = []
        for img_id, score, matched_labels in scored_results[:limit]:
            img_entity = get_image_by_id(self.db, img_id)
            if img_entity:
                img_dict = img_entity.to_dict()
                img_dict["similarity_score"] = round(score, 3)
                img_dict["matched_labels"] = matched_labels
                output.append(img_dict)

        return output

    def ask_images(self, question: str) -> QueryResult:
        """Process conversational question using the rule-based parameterised query parser."""
        return parse_and_execute_query(question=question, session=self.db)
