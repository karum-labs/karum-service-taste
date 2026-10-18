"""Derived inference helpers: name matching, rank decay, and distances.

Seed resolution and tag resolution both derive a confidence from rank plus
name match (PLAN.md §8, §9) — ``/search`` and ``/v2/tags`` publish no score
for these rows. The rules stay deliberately simple and are pinned by tests so
the same inputs always produce the same confidence and the same order. Every
value produced here is a model inference, labeled as such in the responses.
"""

from __future__ import annotations

import difflib
import math
import re
import unicodedata

# Each further rank multiplies the derived confidence by this factor; rank 1
# keeps the name score itself. Upstream rows arrive best-match first.
_RANK_DECAY = 0.85

# Character-level ratios over-trust shared long tokens ("… mezcal"), so for
# multi-token pairs the ratio counts at 60 % and token overlap carries the
# rest. Single-token pairs (typos like "ceramcs") trust the ratio directly.
_RATIO_MULTI_TOKEN_WEIGHT = 0.6

# A prefix match only scores high when it covers most of the longer string:
# "Madre Mezcal" -> "Madre Mezcaleria" is a match, "Kettl" -> "Kettlebell
# Kings" is the recorded false positive (a Kettl brand search returned kettle
# brands) and must stay weak.
_PREFIX_MIN_COVERAGE = 0.6

# A derived confidence below this is unsafe to auto-confirm; the seed builder
# asks the operator to pick instead (PLAN.md §8).
LOW_CONFIDENCE = 0.6

# City membership is checked by distance from the preset point: "Brooklyn"
# rows carry the "New York" geocode city, so a string compare would fail.
IN_CITY_RADIUS_M = 50_000.0

_PUNCTUATION = re.compile(r"[^a-z0-9]+")


def normalize_text(value: str) -> str:
    """Casefold, drop accents, and collapse punctuation to single spaces."""
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_only = decomposed.encode("ascii", "ignore").decode("ascii").lower()
    return _PUNCTUATION.sub(" ", ascii_only).strip()


def name_similarity(query: str, name: str) -> float:
    """Score how well ``name`` matches ``query`` on a 0-1 scale.

    The cascade is pinned by tests: exact match, prefix, whole-token
    containment, then token overlap and a character ratio.
    """
    q = normalize_text(query)
    n = normalize_text(name)
    if not q or not n:
        return 0.0
    if q == n:
        return 1.0
    shorter, longer = (q, n) if len(q) <= len(n) else (n, q)
    if (
        len(shorter) >= 4
        and longer.startswith(shorter)
        and len(shorter) / len(longer) >= _PREFIX_MIN_COVERAGE
    ):
        return 0.9
    q_tokens = set(q.split())
    n_tokens = set(n.split())
    if q_tokens <= n_tokens:
        return 0.85
    jaccard = len(q_tokens & n_tokens) / len(q_tokens | n_tokens)
    ratio = difflib.SequenceMatcher(None, q, n).ratio()
    if len(q_tokens) > 1 and len(n_tokens) > 1:
        ratio *= _RATIO_MULTI_TOKEN_WEIGHT
    return max(jaccard, ratio)


def rank_decay(rank: int) -> float:
    """Rank 1 keeps the name score; each further rank decays it."""
    if rank < 1:
        raise ValueError("rank is 1-based")
    return _RANK_DECAY ** (rank - 1)


def derived_confidence(query: str, name: str, rank: int) -> float:
    """The derived confidence for one row: name match decayed by rank."""
    return round(name_similarity(query, name) * rank_decay(rank), 4)


def haversine_meters(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance between two ``(lat, lon)`` points, in metres."""
    lat1, lon1 = a
    lat2, lon2 = b
    earth_radius_m = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    h = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * earth_radius_m * math.asin(math.sqrt(h))


def in_city(
    location: tuple[float, float] | None,
    point: tuple[float, float] | None,
    *,
    radius_m: float = IN_CITY_RADIUS_M,
) -> bool:
    """Whether a row's point sits inside the preset city.

    A row without a point cannot be verified, so it reports ``False``.
    """
    if location is None or point is None:
        return False
    return haversine_meters(location, point) <= radius_m
