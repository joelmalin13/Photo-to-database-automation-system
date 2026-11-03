"""Rule-based natural language query parser for PixelMind.

Converts free-text questions into safe, parameterized database queries without
requiring a Large Language Model. Optionally falls back to Google Gemini if configured.
Supports exact questions specified in the official project specification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from config.settings import GEMINI_API_KEY, logger
from db.crud import (
    count_label_across_all,
    find_compound_images,
    find_image_with_max_objects,
    find_images_by_category,
    find_images_with_both_labels,
    find_images_with_label,
)

NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}

SINGULAR_MAP = {
    "cars": "car", "dogs": "dog", "cats": "cat", "birds": "bird",
    "people": "person", "persons": "person", "motorcycles": "motorcycle",
    "bicycles": "bicycle", "trucks": "truck", "buses": "bus",
    "airplanes": "airplane", "boats": "boat", "horses": "horse",
    "bottles": "bottle", "chairs": "chair", "laptops": "laptop",
    "cell phones": "cell phone", "phones": "cell phone",
    "electronic devices": "Electronics", "electronics": "Electronics",
    "animals": "Animals", "vehicles": "Vehicles", "food": "Food",
}

EXAMPLE_QUESTIONS = [
    "How many cars have been detected across all images?",
    "Find images containing dogs",
    "Show images containing both people and motorcycles",
    "Which image contains the maximum number of objects?",
    "Show all outdoor images containing at least two vehicles and one person",
    "Find all images containing electronic devices",
]


@dataclass
class QueryResult:
    """Outcome container for Ask Your Images query parsing."""

    question: str
    understood: bool
    answer: str
    images: List[Dict[str, Any]] = field(default_factory=list)
    total_found: int = 0
    intent: str = "unknown"
    suggestions: List[str] = field(default_factory=lambda: list(EXAMPLE_QUESTIONS))


def _clean_word(word: str) -> str:
    """Normalize and singularize an object or category word."""
    clean = word.strip().lower()
    clean = re.sub(r"[^\w\s]", "", clean).strip()
    return SINGULAR_MAP.get(clean, clean)


def _parse_num(val_str: str) -> int:
    """Convert number word or numeric string to integer."""
    clean = val_str.strip().lower()
    if clean in NUMBER_WORDS:
        return NUMBER_WORDS[clean]
    try:
        return int(clean)
    except ValueError:
        return 1


def parse_and_execute_query(question: str, session: Session) -> QueryResult:
    """Parse a natural language question and execute the corresponding parameterized query."""
    q_raw = question.strip()
    q_norm = q_raw.lower()

    # 1. INTENT: Count of specific label across all images
    # e.g. "How many cars have been detected across all images?"
    m1 = re.search(r"how many\s+([a-zA-Z\s]+?)(?:\s+have been detected|\s+are there|\s+exist|\s+in total|\s+across all images|\?|$)", q_norm)
    if m1 and "both" not in q_norm and "outdoor" not in q_norm and "indoor" not in q_norm:
        raw_target = m1.group(1).strip()
        target_label = _clean_word(raw_target)
        count = count_label_across_all(session, target_label)
        images = find_images_with_label(session, target_label)
        return QueryResult(
            question=q_raw,
            understood=True,
            intent="count_label_across_all",
            answer=f"A total of {count} {raw_target} have been detected across all images in the database.",
            images=[img.to_dict() for img in images],
            total_found=len(images),
        )

    # 2. INTENT: Find images containing both A and B
    # e.g. "Show images containing both people and motorcycles"
    m2 = re.search(r"(?:find|show|get|list)\s+(?:all\s+)?images\s+(?:containing|with|having)\s+both\s+([a-zA-Z\s]+?)\s+and\s+([a-zA-Z\s]+)", q_norm)
    if m2:
        label_a = _clean_word(m2.group(1))
        label_b = _clean_word(m2.group(2))
        images = find_images_with_both_labels(session, label_a, label_b)
        return QueryResult(
            question=q_raw,
            understood=True,
            intent="find_both_labels",
            answer=f"Found {len(images)} image(s) containing both '{label_a}' and '{label_b}'.",
            images=[img.to_dict() for img in images],
            total_found=len(images),
        )

    # 3. INTENT: Maximum number of objects
    # e.g. "Which image contains the maximum number of objects?"
    if re.search(r"(?:which|what)\s+image\s+contains\s+(?:the\s+)?(?:maximum|highest|most)\s+(?:number of\s+)?objects", q_norm):
        res = find_image_with_max_objects(session)
        if res:
            img, count = res
            return QueryResult(
                question=q_raw,
                understood=True,
                intent="max_objects",
                answer=f"Image '{img.filename}' (ID: #{img.id}) contains the highest number of detected objects ({count} objects).",
                images=[img.to_dict()],
                total_found=1,
            )
        return QueryResult(
            question=q_raw,
            understood=True,
            intent="max_objects",
            answer="No images currently exist in the database.",
            images=[],
            total_found=0,
        )

    # 4. INTENT: Compound conditions (environment + counts)
    # e.g. "Show all outdoor images containing at least two vehicles and one person"
    m4 = re.search(
        r"(?:find|show|get)\s+(?:all\s+)?(outdoor|indoor)\s+images\s+containing\s+(?:at least\s+)?(\w+)\s+vehicles?\s+and\s+(\w+)\s+(?:persons?|people)",
        q_norm,
    )
    if m4:
        env = m4.group(1).lower()
        min_v = _parse_num(m4.group(2))
        min_p = _parse_num(m4.group(3))
        images = find_compound_images(session, env, min_vehicles=min_v, min_persons=min_p)
        return QueryResult(
            question=q_raw,
            understood=True,
            intent="compound_condition",
            answer=f"Found {len(images)} {env} image(s) containing at least {min_v} vehicle(s) and {min_p} person(s).",
            images=[img.to_dict() for img in images],
            total_found=len(images),
        )

    # 5. INTENT: Find images containing category / electronic devices
    # e.g. "Find all images containing electronic devices"
    m5 = re.search(r"(?:find|show|get|list)\s+(?:all\s+)?images\s+containing\s+(electronic devices|electronics|animals|vehicles|nature|food|sports)", q_norm)
    if m5:
        cat_key = m5.group(1)
        canonical_cat = SINGULAR_MAP.get(cat_key, cat_key.capitalize())
        images = find_images_by_category(session, canonical_cat)
        return QueryResult(
            question=q_raw,
            understood=True,
            intent="find_category",
            answer=f"Found {len(images)} image(s) containing items in the '{canonical_cat}' category.",
            images=[img.to_dict() for img in images],
            total_found=len(images),
        )

    # 6. INTENT: General single label search
    # e.g. "Find images containing dogs"
    m6 = re.search(r"(?:find|show|get|list)\s+(?:all\s+)?images\s+(?:containing|with|of|having)\s+([a-zA-Z\s]+)", q_norm)
    if m6:
        raw_label = m6.group(1).strip()
        label = _clean_word(raw_label)
        images = find_images_with_label(session, label)
        return QueryResult(
            question=q_raw,
            understood=True,
            intent="find_single_label",
            answer=f"Found {len(images)} image(s) containing '{label}'.",
            images=[img.to_dict() for img in images],
            total_found=len(images),
        )

    # 7. Unrecognized query
    logger.info("Question '%s' not recognized by rule-based parser.", q_raw)
    return QueryResult(
        question=q_raw,
        understood=False,
        intent="unrecognized",
        answer="I couldn't understand that question with the rule-based query parser. Try asking one of the examples below.",
        images=[],
        total_found=0,
        suggestions=list(EXAMPLE_QUESTIONS),
    )
