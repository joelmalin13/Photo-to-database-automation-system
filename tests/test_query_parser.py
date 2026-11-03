"""Unit tests for the rule-based Ask Your Images natural language query parser.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from core.query_parser import parse_and_execute_query
from db.crud import add_detections, create_image
from db.models import Base


@pytest.fixture
def db_session() -> Session:
    """Provide isolated in-memory SQLite database session populated with test records."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    # Populate test images
    img1 = create_image(
        session,
        filename="outdoor_cars_person.png",
        stored_path="uploads/test1.png",
        annotated_path="annotated/test1.png",
        sha256="hash1111111111111111111111111111111111111111111111111111111111111111",
        phash="0123456789abcdef",
        width=800,
        height=600,
        category="Vehicles",
        scene="street",
        environment="outdoor",
    )
    add_detections(session, img1.id, [
        {"label": "car", "category": "Vehicles", "count": 2, "avg_confidence": 0.95},
        {"label": "person", "category": "Human activities", "count": 1, "avg_confidence": 0.88},
        {"label": "motorcycle", "category": "Vehicles", "count": 1, "avg_confidence": 0.82},
    ])

    img2 = create_image(
        session,
        filename="park_dogs.png",
        stored_path="uploads/test2.png",
        annotated_path="annotated/test2.png",
        sha256="hash2222222222222222222222222222222222222222222222222222222222222222",
        phash="fedcba9876543210",
        width=800,
        height=600,
        category="Animals",
        scene="park",
        environment="outdoor",
    )
    add_detections(session, img2.id, [
        {"label": "dog", "category": "Animals", "count": 3, "avg_confidence": 0.92},
    ])

    img3 = create_image(
        session,
        filename="office_laptop.png",
        stored_path="uploads/test3.png",
        annotated_path="annotated/test3.png",
        sha256="hash3333333333333333333333333333333333333333333333333333333333333333",
        phash="1111222233334444",
        width=800,
        height=600,
        category="Electronics",
        scene="office",
        environment="indoor",
    )
    add_detections(session, img3.id, [
        {"label": "laptop", "category": "Electronics", "count": 2, "avg_confidence": 0.91},
    ])

    session.commit()
    yield session
    session.close()


def test_question_count_cars_across_all(db_session: Session):
    """Test Question 1: 'How many cars have been detected across all images?'"""
    res = parse_and_execute_query("How many cars have been detected across all images?", db_session)
    assert res.understood is True
    assert "2 cars" in res.answer or "2" in res.answer
    assert res.intent == "count_label_across_all"


def test_question_find_dogs(db_session: Session):
    """Test Question 2: 'Find images containing dogs'"""
    res = parse_and_execute_query("Find images containing dogs", db_session)
    assert res.understood is True
    assert res.total_found == 1
    assert res.images[0]["filename"] == "park_dogs.png"


def test_question_both_people_and_motorcycles(db_session: Session):
    """Test Question 3: 'Show images containing both people and motorcycles'"""
    res = parse_and_execute_query("Show images containing both people and motorcycles", db_session)
    assert res.understood is True
    assert res.total_found == 1
    assert res.images[0]["filename"] == "outdoor_cars_person.png"


def test_question_maximum_objects(db_session: Session):
    """Test Question 4: 'Which image contains the maximum number of objects?'"""
    res = parse_and_execute_query("Which image contains the maximum number of objects?", db_session)
    assert res.understood is True
    assert "outdoor_cars_person.png" in res.answer or "park_dogs.png" in res.answer
    assert res.total_found == 1


def test_question_compound_outdoor_vehicles_and_person(db_session: Session):
    """Test Question 5: 'Show all outdoor images containing at least two vehicles and one person'"""
    res = parse_and_execute_query("Show all outdoor images containing at least two vehicles and one person", db_session)
    assert res.understood is True
    assert res.total_found == 1
    assert res.images[0]["filename"] == "outdoor_cars_person.png"


def test_question_find_electronic_devices(db_session: Session):
    """Test Question 6: 'Find all images containing electronic devices'"""
    res = parse_and_execute_query("Find all images containing electronic devices", db_session)
    assert res.understood is True
    assert res.total_found == 1
    assert res.images[0]["filename"] == "office_laptop.png"


def test_question_unrecognized(db_session: Session):
    """Test handling of unsupported/nonsensical questions with helpful suggestions."""
    res = parse_and_execute_query("What is the meaning of life and universe?", db_session)
    assert res.understood is False
    assert len(res.suggestions) > 0
