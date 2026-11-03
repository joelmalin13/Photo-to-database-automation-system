"""Multimodal visual and semantic embedding engine for PixelMind.

Supports dual operating modes:
- Cloud Mode: CloudEmbedder (Google Gemini text-embedding-004 / gemini-embedding-001)
- Local Mode: LocalEmbedder (OpenCLIP ViT-B-32 with lazy torch/open_clip imports)
All embeddings are stored and compared as normalized Python lists of floats (JSON-portable).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import hashlib
import io
from pathlib import Path
from typing import Any, List, Optional, Union
import numpy as np
from PIL import Image as PILImage

from config.settings import (
    AI_MODE,
    CLIP_MODEL_NAME,
    CLIP_PRETRAINED,
    GEMINI_API_KEY,
    GEMINI_EMBED_MODEL,
    logger,
)
from core.decorators import timed
from core.exceptions import EmbedderError


class BaseEmbedder(ABC):
    """Abstract interface defining semantic embedding contracts."""

    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Generate normalized embedding vector for a natural language string."""
        raise NotImplementedError

    @abstractmethod
    def embed_image_metadata(
        self,
        image_input: Any,
        caption: Optional[str] = None,
        objects: Optional[List[str]] = None,
        scene: Optional[str] = None,
        environment: Optional[str] = None,
    ) -> List[float]:
        """Generate normalized embedding vector for an image or its visual semantics."""
        raise NotImplementedError

    def compute_similarity(self, vec_a: Any, vec_b: Any) -> float:
        """Compute normalized cosine similarity between two float vectors in [0.0, 1.0]."""
        if vec_a is None or vec_b is None:
            return 0.0
        try:
            if len(vec_a) == 0 or len(vec_b) == 0:
                return 0.0
            a = np.asarray(vec_a, dtype=np.float32)
            b = np.asarray(vec_b, dtype=np.float32)
            norm_a = float(np.linalg.norm(a))
            norm_b = float(np.linalg.norm(b))
            if norm_a == 0 or norm_b == 0:
                return 0.0
            min_dim = min(len(a), len(b))
            dot = float(np.dot(a[:min_dim], b[:min_dim]) / (norm_a * norm_b))
            return round(float(max(0.0, min(1.0, (dot + 1.0) / 2.0))), 3)
        except Exception:
            return 0.0

    def _pseudo_embed(self, seed_str: str, dim: int = 512) -> List[float]:
        """Generate a deterministic normalized vector for fallback/tests without external APIs."""
        raw = seed_str.encode("utf-8")
        repeats = (dim // 64) + 1
        digest = b"".join(hashlib.sha512(raw + str(i).encode()).digest() for i in range(repeats))
        # Convert uint8 bytes to normalized [-1.0, 1.0] floats
        arr = np.frombuffer(digest[:dim], dtype=np.uint8).astype(np.float32) / 128.0 - 1.0
        if len(arr) < dim:
            arr = np.pad(arr, (0, dim - len(arr)), "constant")
        norm = float(np.linalg.norm(arr))
        if norm > 0:
            arr = arr / norm
        return arr.tolist()


class CloudEmbedder(BaseEmbedder):
    """Cloud embedding implementation using Google Gemini embedding models."""

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None) -> None:
        self.api_key = api_key or GEMINI_API_KEY
        self.model_name = model_name or GEMINI_EMBED_MODEL
        self._client: Optional[Any] = None

    def _get_client(self) -> Any:
        if self._client is None:
            if not self.api_key:
                logger.warning("GEMINI_API_KEY is not set. CloudEmbedder will use deterministic pseudo-embeddings.")
                return None
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except Exception as exc:
                logger.warning("Failed to initialize Google GenAI Client: %s", exc)
                return None
        return self._client

    @timed
    def embed_text(self, text: str) -> List[float]:
        """Generate text embedding vector using Gemini."""
        clean_text = text.strip()
        if not clean_text:
            return [0.0] * 512

        client = self._get_client()
        if client is None:
            return self._pseudo_embed(clean_text, dim=768)

        try:
            res = client.models.embed_content(
                model=self.model_name,
                contents=clean_text,
            )
            # Access embedding values
            values: Optional[List[float]] = None
            if hasattr(res, "embedding") and res.embedding and hasattr(res.embedding, "values"):
                values = res.embedding.values
            elif hasattr(res, "embeddings") and res.embeddings and hasattr(res.embeddings[0], "values"):
                values = res.embeddings[0].values

            if not values:
                return self._pseudo_embed(clean_text, dim=768)

            vec = np.array(values, dtype=np.float32)
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            return vec.tolist()
        except Exception as exc:
            logger.warning("Gemini text embedding call failed (%s). Falling back to pseudo-embed.", exc)
            return self._pseudo_embed(clean_text, dim=768)

    @timed
    def embed_image_metadata(
        self,
        image_input: Any,
        caption: Optional[str] = None,
        objects: Optional[List[str]] = None,
        scene: Optional[str] = None,
        environment: Optional[str] = None,
    ) -> List[float]:
        """Generate semantic embedding by combining caption, detected objects, and scene setting."""
        parts: List[str] = []
        if caption:
            parts.append(caption.strip())
        if objects:
            parts.append(f"Visual objects detected: {', '.join(objects)}.")
        if scene:
            env_str = f" in {environment}" if environment else ""
            parts.append(f"Scene setting: {scene}{env_str}.")

        combined_desc = " ".join(parts).strip()
        if not combined_desc:
            combined_desc = "Photograph showing natural and human environment."
        return self.embed_text(combined_desc)


class LocalEmbedder(BaseEmbedder):
    """Local OpenCLIP embedding engine with lazy PyTorch imports."""

    _instance: Optional[LocalEmbedder] = None
    _model: Any = None
    _preprocess: Any = None
    _tokenizer: Any = None
    _device: str = "cpu"

    @classmethod
    def get_instance(cls) -> LocalEmbedder:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return

        try:
            import torch
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
        except ImportError as exc:
            logger.warning("PyTorch/OpenCLIP not installed (%s). LocalEmbedder will use pseudo-embeddings.", exc)
            self._model = None
        except Exception as exc:
            logger.warning("Could not load open_clip model (%s). Using fallback pseudo-embedder.", exc)
            self._model = None

    @timed
    def embed_text(self, text: str) -> List[float]:
        self._ensure_loaded()
        if self._model is None or self._tokenizer is None:
            return self._pseudo_embed(text, dim=512)

        try:
            import torch
            tokens = self._tokenizer([text]).to(self._device)
            with torch.no_grad():
                text_features = self._model.encode_text(tokens)
                text_features /= text_features.norm(dim=-1, keepdim=True)
            return text_features.cpu().numpy().flatten().tolist()
        except Exception as exc:
            logger.warning("Local text embedding failed: %s", exc)
            return self._pseudo_embed(text, dim=512)

    @timed
    def embed_image_metadata(
        self,
        image_input: Any,
        caption: Optional[str] = None,
        objects: Optional[List[str]] = None,
        scene: Optional[str] = None,
        environment: Optional[str] = None,
    ) -> List[float]:
        self._ensure_loaded()
        if self._model is None or self._preprocess is None:
            seed = caption or (image_input if isinstance(image_input, str) else "local_image")
            return self._pseudo_embed(str(seed), dim=512)

        try:
            import torch
            if isinstance(image_input, (str, Path)):
                pil_img = PILImage.open(str(image_input)).convert("RGB")
            elif isinstance(image_input, bytes):
                pil_img = PILImage.open(io.BytesIO(image_input)).convert("RGB")
            elif isinstance(image_input, PILImage.Image):
                pil_img = image_input.convert("RGB")
            else:
                return self._pseudo_embed("image", dim=512)

            tensor_img = self._preprocess(pil_img).unsqueeze(0).to(self._device)
            with torch.no_grad():
                image_features = self._model.encode_image(tensor_img)
                image_features /= image_features.norm(dim=-1, keepdim=True)
            return image_features.cpu().numpy().flatten().tolist()
        except Exception as exc:
            logger.warning("Local image embedding failed: %s", exc)
            return self._pseudo_embed("image_error", dim=512)

    def zero_shot_classify(
        self, image_input: Any, candidate_labels: List[str]
    ) -> Tuple[str, float]:
        """Perform zero-shot classification over candidate text labels."""
        self._ensure_loaded()
        if self._model is None:
            return candidate_labels[0] if candidate_labels else "General", 0.5

        try:
            import torch
            if isinstance(image_input, (str, Path)):
                pil_img = PILImage.open(str(image_input)).convert("RGB")
            elif isinstance(image_input, bytes):
                pil_img = PILImage.open(io.BytesIO(image_input)).convert("RGB")
            else:
                pil_img = image_input.convert("RGB")

            tensor_img = self._preprocess(pil_img).unsqueeze(0).to(self._device)
            text_prompts = [f"a photo of {lbl}" for lbl in candidate_labels]
            tokens = self._tokenizer(text_prompts).to(self._device)

            with torch.no_grad():
                img_feat = self._model.encode_image(tensor_img)
                txt_feat = self._model.encode_text(tokens)
                img_feat /= img_feat.norm(dim=-1, keepdim=True)
                txt_feat /= txt_feat.norm(dim=-1, keepdim=True)
                similarity = (100.0 * img_feat @ txt_feat.T).softmax(dim=-1)

            scores = similarity.cpu().numpy().flatten()
            best_idx = int(np.argmax(scores))
            return candidate_labels[best_idx], round(float(scores[best_idx]), 3)
        except Exception:
            return candidate_labels[0] if candidate_labels else "General", 0.5


# Backwards-compatible alias for existing imports
ClipEmbedder = LocalEmbedder


def get_embedder(mode: Optional[str] = None) -> BaseEmbedder:
    """Factory returning the appropriate embedding engine."""
    from config.settings import AI_MODE
    import os

    target_mode = (mode or os.getenv("AI_MODE") or AI_MODE).strip().lower()
    if target_mode == "cloud" or bool(os.getenv("VERCEL")):
        return CloudEmbedder()
    return LocalEmbedder.get_instance()
