"""One canonical form per Qloo request.

Two surfaces need the same canonical request shape:

- the fixture transport matches a live-shaped request against the recorded
  ``source.request`` of a fixture, but recordings are not byte-identical to
  what a client emits — parameters arrive percent-encoded, in a different
  order, and with float formatting that varies (``8000`` vs ``8000.0``);
- evidence records (``karum.common.v1.EvidenceCall.parameters``) want a
  stable, redaction-safe request signature.

Canonicalisation is value-aware: numbers compare as numbers, ``POINT(lon
lat)`` and bare ``lat,lon`` pairs compare as coordinate tuples (tagged by
form, because the two surfaces differ — DI-21), and comma-separated lists of
URNs or ids compare order-independently.

The formatting helpers mirror what the recordings show so that live traffic
and the fixture pack speak the same spellings.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import parse_qsl

_POINT_RE = re.compile(r"^POINT\s*\(\s*(?P<lon>-?\d+(?:\.\d+)?)\s+(?P<lat>-?\d+(?:\.\d+)?)\s*\)$")
_PAIR_RE = re.compile(r"^(?P<lat>-?\d+(?:\.\d+)?)\s*,\s*(?P<lon>-?\d+(?:\.\d+)?)$")

#: Parameters whose values are plain numbers; compared with float equality.
_NUMERIC_PARAMS = frozenset({"take", "page", "filter.radius", "filter.location.radius"})

#: Parameters whose values are comma-separated lists of URNs or ids.
_LIST_PARAMS = frozenset(
    {
        "types",
        "filter.tags",
        "filter.tag.types",
        "filter.results.entities",
        "filter.exclude.entities",
        "signal.interests.entities",
        "signal.interests.tags",
        "a.signal.interests.entities",
        "b.signal.interests.entities",
        "output.heatmap.boundary",
    }
)

#: A canonical request signature: the path plus normalised (name, value) pairs.
RequestSignature = tuple[str, tuple[tuple[str, object], ...]]


def parse_request(request: str) -> tuple[str, list[tuple[str, str]]]:
    """Split a recorded ``source.request`` into path and raw parameter pairs."""
    path, _, query = request.partition("?")
    return path, parse_qsl(query, keep_blank_values=True)


def _normalise(name: str, value: str) -> object:
    if name in _NUMERIC_PARAMS:
        try:
            return float(value)
        except ValueError:
            return value
    if name == "filter.location":
        # Insights uses WKT with longitude first; /search uses a bare
        # latitude-first pair (DI-21). Tag the forms so they never collide.
        point = _POINT_RE.match(value)
        if point:
            return (
                "point",
                round(float(point["lon"]), 7),
                round(float(point["lat"]), 7),
            )
        pair = _PAIR_RE.match(value)
        if pair:
            return (
                "pair",
                round(float(pair["lat"]), 7),
                round(float(pair["lon"]), 7),
            )
        return value
    if name in _LIST_PARAMS:
        return tuple(sorted(part.strip() for part in value.split(",") if part.strip()))
    return value


def signature(
    path_or_request: str,
    params: Sequence[tuple[str, str]] | Mapping[str, str] | None = None,
) -> RequestSignature:
    """The canonical signature of a request.

    Pass a full request string, or a path plus parameter pairs/mapping.
    """
    if params is None:
        path, pairs = parse_request(path_or_request)
    else:
        path = path_or_request
        pairs = list(params.items()) if isinstance(params, Mapping) else list(params)
    normalised = sorted(((name, _normalise(name, value)) for name, value in pairs), key=_name)
    return path, tuple(normalised)


def _name(item: tuple[str, object]) -> str:
    return item[0]


def format_params(params: Sequence[tuple[str, str]]) -> str:
    """A stable ``k=v&...`` string for evidence records (never credentials)."""
    return "&".join(f"{name}={value}" for name, value in sorted(params, key=_name))


def format_number(value: float) -> str:
    """Format a radius or count the way the recordings show it (``8000``)."""
    return f"{value:g}"


def format_point(lon: float, lat: float) -> str:
    """WKT ``POINT(lon lat)`` — insights calls (longitude first, DI-21)."""
    return f"POINT({lon:g} {lat:g})"


def format_pair(lat: float, lon: float) -> str:
    """Bare ``lat,lon`` — /search only (latitude first, DI-21)."""
    return f"{lat:g},{lon:g}"


def format_list(values: Sequence[str]) -> str:
    """Comma-join URNs or ids the way the recordings show them."""
    return ",".join(values)


def _jsonable(value: Any) -> Any:
    """Convert a canonical signature value into JSON-friendly nesting."""
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def cache_key(path: str, params: Sequence[tuple[str, str]]) -> str:
    """A stable, collision-resistant cache key for a Qloo request.

    The key is ``karum:qloo:<sha256>`` over the canonical request signature,
    so the same logical request (regardless of parameter ordering or float
    formatting) always hits the same entry.
    """
    sig: RequestSignature = signature(path, params)
    path_value, pairs = sig
    document = [path_value, [[name, _jsonable(value)] for name, value in pairs]]
    digest = hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"karum:qloo:{digest}"
