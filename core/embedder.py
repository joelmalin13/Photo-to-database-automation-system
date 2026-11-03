"""CLIP visual and textual embedding engine for PixelMind.

Generates 512-dimensional normalized embeddings for images and natural language text,
enabling semantic cross-modal search, zero-shot scene categorization, and visual similarity.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, List, Optional, Tuple, Union
import numpy as np
from PIL import Image
import torch

from config.settings import CLIP_MODEL_NAME, CLIP_PRETRAINED, logger
from core.decorators import timed
from core.exceptions import EmbedderError


class ClipEmbedder:
    """Singleton wrapper for open_clip model and tokenizer."""

    _instance: Optional[ClipEmbedder] = None
    _model: Any = None
    _preprocess: Any = None
    _tokenizer: Any = None
    _device: str = "cpu"

    @classmethod
    def get_instance(cls) -> ClipEmbedder:
        """Retrieve or initialize the ClipEmbedder singleton."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        """Initialize CLIP model lazily."""
        self._ensure_loaded()

    def _ensure_loaded(self) -> None:
        """Load open_clip model, weights, and tokenizer if not already initialized."""
        if self._model is not None:
            return

        try:
            import open_clip

            logger.info("Loading CLIP model (%s, pretrained=%s)...", CLIP_MODEL_NAME, CLIP_PRETRAINED)
            model, _, preprocess = open_clip.create_model_and_transforms(
                CLIP_MODEL_NAME, pretrained=CLIP_PRETRAINED, device=self._device
            )
            tokenizer = open_clip.get_tokenizer(CLIP_MODEL_NAME)
            model.eval()

            self._model = model
            self._preprocess = preprocess
            self._tokenizer = tokenizer
            logger.info("CLIP model and tokenizer initialized successfully.")

        except Exception as exc:
            logger.warning(
                "Could not load open_clip model (%s). Using fallback pseudo-embedder.",
                exc,
            )
            self._model = None

    def _pseudo_embed(self, seed_str: str) -> np.ndarray:
        """Generate a deterministic 512-dimensional normalized vector for fallback/tests."""
        hasher = hashlib.sha512(seed_str.encode("utf-8")).digest()
        # Repeat to reach 512 floats
        seed_ints = np.frombuffer(hasher * 8, dtype=np.uint8)[:512].astype(np.float32)
        vec = (seed_ints - 128.0) / 128.0
        norm = np.linalg.norm(vec)
        return vec / (norm if norm > 0 else 1.0)

    @timed
    def embed_image(self, image_input: Union[Path, str, Image.Image]) -> np.ndarray:
        """Generate a 512-dimensional normalized float32 embedding for an image."""
        self._ensure_loaded()

        if isinstance(image_input, (str, Path)):
            path = Path(image_input)
            if not path.exists():
                raise EmbedderError(f"Image not found at {path}")
            try:
                pil_img = Image.open(path).convert("RGB")
            except Exception as exc:
                raise EmbedderError(f"Failed to open image: {exc}") from exc
        else:
            pil_img = image_input.convert("RGB")

        if self._model is None or self._preprocess is None:
            return self._pseudo_embed(str(pil_img.size))

        try:
            tensor_img = self._preprocess(pil_img).unsqueeze(0).to(self._device)
            with torch.no_grad():
                features = self._model.encode_image(tensor_img)
                features /= features.norm(dim=-1, keepdim=True)
            return features.cpu().numpy()[0].astype(np.float32)

        except Exception as exc:
            logger.error("CLIP image encoding failed: %s", exc)
            return self._pseudo_embed(f"err_{exc}")

    @timed
    def embed_text(self, text: str) -> np.ndarray:
        """Generate a 512-dimensional normalized float32 embedding for natural language text."""
        self._ensure_loaded()
        clean_text = text.strip()
        if not clean_text:
            clean_text = "photo"

        if self._model is None or self._tokenizer is None:
            return self._pseudo_embed(clean_text)

        try:
            tokens = self._tokenizer([clean_text]).to(self._device)
            with torch.no_grad():
                features = self._model.encode_text(tokens)
                features /= features.norm(dim=-1, keepdim=True)
            return features.cpu().numpy()[0].astype(np.float32)

        except Exception as exc:
            logger.error("CLIP text encoding failed: %s", exc)
            return self._pseudo_embed(clean_text)

    def compute_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two normalized embedding vectors."""
        if vec1 is None or vec2 is None:
            return 0.0
        try:
            dot = float(np.dot(vec1, vec2))
            return max(0.0, min(1.0, (dot + 1.0) / 2.0))  # Rescaled [0, 1]
        except Exception:
            return 0.0

    def zero_shot_classify(
        self,
        image_input: Union[Path, str, Image.Image],
        candidate_labels: List[str],
    ) -> Tuple[str, float]:
        """Perform zero-shot classification comparing image against candidate labels."""
        if not candidate_labels:
            return "general", 0.5

        img_vec = self.embed_image(image_input)
        best_label = candidate_labels[0]
        best_score = -1.0

        for label in candidate_labels:
            prompt = f"a photo of a {label}"
            text_vec = self.embed_text(prompt)
            sim = self.compute_similarity(img_vec, text_vec)
            if sim > best_score:
                best_score = sim
                best_label = label

        return best_label, round(best_score, 3)
