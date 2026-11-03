"""Reverse visual intelligence and similarity matching service for PixelMind.

Implements reverse image search across four selectable modes:
1. Object similarity (Jaccard index on object counts and labels)
2. Colour similarity (Palette Euclidean distance in RGB space)
3. Scene similarity (Scene category and environment match)
4. Overall similarity (Cosine distance across semantic embedding vectors)
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from PIL import Image as PILImage
from sqlalchemy.orm import Session

from core.detector_base import get_detector
from core.dna import extract_dominant_colors
from core.embedder import get_embedder
from core.similarity import (
    compute_color_similarity,
    compute_object_similarity,
    compute_overall_similarity,
    compute_scene_similarity,
)
from db.crud import get_all_dna_for_similarity, get_image_by_id


class DnaService:
    """Service providing reverse image search and visual fingerprint comparison."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.embedder = get_embedder()

    def find_similar_by_image(
        self,
        image_bytes: bytes,
        mode: str = "overall",
        limit: int = 12,
    ) -> List[Dict[str, Any]]:
        """Find stored images similar to an uploaded query image across the selected mode."""
        stored_items = get_all_dna_for_similarity(self.db)
        if not stored_items:
            return []

        pil_img = PILImage.open(io.BytesIO(image_bytes)).convert("RGB")
        mode_clean = mode.strip().lower()

        scored_results: List[Tuple[Any, float]] = []

        # Mode 1: Object Similarity
        if mode_clean == "object":
            detector = get_detector()
            q_det = detector.detect(pil_img, save_annotated=False)
            q_items = q_det.items

            for img, dna, detections in stored_items:
                sim = compute_object_similarity(q_items, detections)
                scored_results.append((img, sim))

        # Mode 2: Colour Similarity
        elif mode_clean == "color":
            q_colors = extract_dominant_colors(pil_img, num_colors=5)
            for img, dna, detections in stored_items:
                t_colors = (dna.dominant_colors_json if dna else []) or []
                sim = compute_color_similarity(q_colors, t_colors)
                scored_results.append((img, sim))

        # Mode 3: Scene Similarity
        elif mode_clean == "scene":
            detector = get_detector()
            q_det = detector.detect(pil_img, save_annotated=False)
            q_scene = q_det.scene or "general"
            q_env = q_det.environment or "outdoor"

            for img, dna, detections in stored_items:
                sim = compute_scene_similarity(q_scene, q_env, img.scene, img.environment)
                scored_results.append((img, sim))

        # Mode 4: Overall Similarity (Default)
        else:
            detector = get_detector()
            q_det = detector.detect(pil_img, save_annotated=False)
            q_vec = self.embedder.embed_image_metadata(
                image_input=pil_img,
                caption=q_det.caption,
                objects=[it.label for it in q_det.items],
                scene=q_det.scene,
                environment=q_det.environment,
            )

            for img, dna, detections in stored_items:
                t_vec = dna.get_embedding_vector() if dna else None
                if q_vec and t_vec:
                    sim = self.embedder.compute_similarity(q_vec, t_vec)
                else:
                    sim = 0.0
                scored_results.append((img, sim))

        # Sort by similarity descending
        scored_results.sort(key=lambda x: x[1], reverse=True)

        output: List[Dict[str, Any]] = []
        for img, sim in scored_results[:limit]:
            img_dict = img.to_dict()
            img_dict["similarity_score"] = round(sim, 3)
            img_dict["similarity_percentage"] = int(round(sim * 100))
            output.append(img_dict)

        return output

    def find_similar_to_stored(
        self,
        image_id: int,
        mode: str = "overall",
        limit: int = 6,
    ) -> List[Dict[str, Any]]:
        """Find stored images similar to an existing image record."""
        target_img = get_image_by_id(self.db, image_id)
        if not target_img:
            return []

        stored_items = get_all_dna_for_similarity(self.db)
        # Exclude the target image itself
        other_items = [item for item in stored_items if item[0].id != image_id]
        if not other_items:
            return []

        mode_clean = mode.strip().lower()
        scored_results: List[Tuple[Any, float]] = []

        if mode_clean == "object":
            for img, dna, detections in other_items:
                sim = compute_object_similarity(target_img.detections, detections)
                scored_results.append((img, sim))

        elif mode_clean == "color":
            q_colors = (target_img.dna.dominant_colors_json if target_img.dna else []) or []
            for img, dna, detections in other_items:
                t_colors = (dna.dominant_colors_json if dna else []) or []
                sim = compute_color_similarity(q_colors, t_colors)
                scored_results.append((img, sim))

        elif mode_clean == "scene":
            for img, dna, detections in other_items:
                sim = compute_scene_similarity(target_img.scene, target_img.environment, img.scene, img.environment)
                scored_results.append((img, sim))

        else:
            q_vec = target_img.dna.get_embedding_vector() if target_img.dna else None
            for img, dna, detections in other_items:
                t_vec = dna.get_embedding_vector() if dna else None
                if q_vec and t_vec:
                    sim = self.embedder.compute_similarity(q_vec, t_vec)
                else:
                    sim = 0.0
                scored_results.append((img, sim))

        scored_results.sort(key=lambda x: x[1], reverse=True)
        output: List[Dict[str, Any]] = []
        for img, sim in scored_results[:limit]:
            img_dict = img.to_dict()
            img_dict["similarity_score"] = round(sim, 3)
            img_dict["similarity_percentage"] = int(round(sim * 100))
            output.append(img_dict)

        return output
