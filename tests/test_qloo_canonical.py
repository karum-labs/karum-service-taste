"""Canonical request signatures: encoding-, order-, and format-insensitive.

These are the guarantees the fixture transport and the evidence records rely
on: a request the client builds matches the recording it replays even though
recordings differ in percent-encoding, parameter order, and float formatting.
"""

from __future__ import annotations

from karum_service_taste.qloo import canonical


def test_recorded_and_built_requests_share_a_signature() -> None:
    recorded = "/search?query=Aesop&types=urn%3Aentity%3Abrand&take=5&page=1"
    built = [
        ("query", "Aesop"),
        ("types", "urn:entity:brand"),
        ("take", "5"),
        ("page", "1"),
    ]
    assert canonical.signature(recorded) == canonical.signature("/search", built)


def test_parameter_order_is_irrelevant() -> None:
    first = canonical.signature("/v2/tags", [("filter.query", "bar"), ("take", "15")])
    second = canonical.signature("/v2/tags", [("take", "15"), ("filter.query", "bar")])
    assert first == second


def test_numeric_formatting_is_irrelevant() -> None:
    whole = canonical.signature("/v2/insights", [("filter.location.radius", "8000")])
    floaty = canonical.signature("/v2/insights", [("filter.location.radius", "8000.0")])
    assert whole == floaty


def test_rebuilt_point_matches_the_recorded_point() -> None:
    recorded = canonical.signature("/v2/insights?filter.location=POINT(-97.7431%2030.2672)&take=25")
    built = canonical.signature(
        "/v2/insights",
        [("filter.location", canonical.format_point(-97.7431, 30.2672)), ("take", "25")],
    )
    assert recorded == built


def test_bare_pair_is_its_own_form() -> None:
    pair = canonical.signature("/search?filter.location=18.9221%2C72.8317")
    point = canonical.signature("/v2/insights?filter.location=POINT(72.8317%2018.9221)")
    # The same coordinates, but the two documented surfaces (DI-21) must not
    # collide: one is latitude-first, the other longitude-first.
    assert pair != point
    assert (
        canonical.signature(
            "/search", [("filter.location", canonical.format_pair(18.9221, 72.8317))]
        )
        == pair
    )


def test_entity_lists_compare_order_insensitively() -> None:
    one = canonical.signature("/v2/insights", [("signal.interests.entities", "B-ID,A-ID")])
    other = canonical.signature("/v2/insights", [("signal.interests.entities", "A-ID,B-ID")])
    assert one == other


def test_text_values_stay_case_sensitive() -> None:
    upper = canonical.signature("/search", [("query", "Aesop")])
    lower = canonical.signature("/search", [("query", "aesop")])
    assert upper != lower


def test_format_params_is_stable_and_sorted() -> None:
    formatted = canonical.format_params([("take", "25"), ("filter.type", "urn:entity:place")])
    assert formatted == "filter.type=urn:entity:place&take=25"


def test_format_helpers_match_the_recorded_spellings() -> None:
    assert canonical.format_number(8000) == "8000"
    assert canonical.format_number(8000.5) == "8000.5"
    assert canonical.format_point(-73.9566, 40.7172) == "POINT(-73.9566 40.7172)"
    assert canonical.format_pair(18.9221, 72.8317) == "18.9221,72.8317"
    assert canonical.format_list(["A", "B"]) == "A,B"


def test_parse_request_splits_path_and_decodes() -> None:
    path, pairs = canonical.parse_request("/search?query=Leopold%20Cafe&take=5")
    assert path == "/search"
    assert pairs == [("query", "Leopold Cafe"), ("take", "5")]
