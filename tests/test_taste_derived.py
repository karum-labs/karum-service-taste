"""Derived inference rules, pinned so scores never drift silently (PLAN.md §8, §9)."""

from __future__ import annotations

import pytest

from karum_service_taste.taste.derived import (
    LOW_CONFIDENCE,
    derived_confidence,
    haversine_meters,
    in_city,
    name_similarity,
    normalize_text,
    rank_decay,
)


def test_normalize_handles_case_accents_and_punctuation() -> None:
    assert normalize_text("Cafés") == "cafes"
    assert normalize_text("  MUJI  ") == "muji"
    assert normalize_text("Maggie Mae's") == "maggie mae s"


@pytest.mark.parametrize(
    ("query", "name", "expected"),
    [
        ("MUJI", "Muji", 1.0),
        ("Lilia", "Lilia", 1.0),
        ("Madre Mezcal", "Madre Mezcaleria", 0.9),
        ("Coffee Shop", "Coffee shops", 0.9),
        ("Subko", "Mary Lodge by Subko", 0.85),
        ("gallery", "Art gallery", 0.85),
    ],
)
def test_name_similarity_pinned_cases(query: str, name: str, expected: float) -> None:
    assert name_similarity(query, name) == expected


def test_multiword_free_text_scores_above_the_floor() -> None:
    # "Ceramic Studio" is no clean prefix of "Ceramics"; the character ratio
    # still clears the confidence floor that free text must meet.
    assert name_similarity("Ceramic Studio", "Ceramics") == pytest.approx(0.7273, abs=1e-3)
    assert name_similarity("Ceramic Studio", "Ceramics") > LOW_CONFIDENCE


def test_name_similarity_weak_matches_stay_below_the_floor() -> None:
    assert name_similarity("Madre Mezcal", "Hija De Tu Madre") < LOW_CONFIDENCE
    assert name_similarity("Madre Mezcal", "Ilegal Mezcal") < LOW_CONFIDENCE
    assert name_similarity("Kettl", "Kettlebell Kings") < LOW_CONFIDENCE
    assert name_similarity("shoes", "Bar") < LOW_CONFIDENCE


def test_typo_single_tokens_keep_the_character_ratio() -> None:
    assert name_similarity("ceramcs", "Ceramics") > 0.85


def test_rank_decay_and_derived_confidence() -> None:
    assert rank_decay(1) == 1.0
    assert rank_decay(2) == 0.85
    assert derived_confidence("cafe", "Cafe", 1) == 1.0
    assert derived_confidence("cafe", "Cafe", 2) == 0.85
    assert derived_confidence("Kettl", "Kettlebell Kings", 1) == 0.4762
    assert derived_confidence("ceramcs", "Ceramics", 1) > LOW_CONFIDENCE
    with pytest.raises(ValueError):
        rank_decay(0)


def test_haversine_and_in_city() -> None:
    austin = (30.2672, -97.7431)
    near = (30.2672, -97.7400)
    assert haversine_meters(austin, austin) == 0.0
    assert 250 < haversine_meters(austin, near) < 350
    assert in_city(near, austin) is True
    # The Brooklyn Lilia row is New York; the same name also resolves to Rio.
    assert in_city((40.7175365, -73.9524225), (40.7172, -73.9566)) is True
    assert in_city((-22.9091795, -43.1840067), (40.7172, -73.9566)) is False
    # A row without a point cannot be verified; neither can a missing point.
    assert in_city(None, austin) is False
    assert in_city(austin, None) is False
    assert in_city(near, austin, radius_m=1.0) is False  # ~298 m away
