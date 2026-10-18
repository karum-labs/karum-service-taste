"""Locality heatmap (PLAN.md section 12): density cells and corridor polygons.

``GetLocalityHeatmap`` re-runs the flagship heatmap exactly as the lock pass
recorded it: ``filter.type=urn:heatmap`` with the seed, the point as WKT, the
preset 10 km radius, and ``take=50``. Cells are the density layer the map
renders. ``output.heatmap.boundary=urn:entity:locality`` is a second call
whose rows are locality polygons — a handful land as bare points, which keep
their centroid and carry no ring — and the strongest of those become the
corridors the site-selection brief names.

Corridor selection is deterministic: localities rank by affinity (the
response order breaks ties), a repeated name or an identical polygon
collapses to its strongest occurrence, only polygons whose centroid falls
inside the requested radius count (the transport returns state-sized shapes
too), and the list stops at ``corridor_limit``. Anchors are the strongest
already-ranked places whose point falls inside one of those corridors; the
caller supplies them, so the run's own door board is what anchors the map.

The campaign never dies here (PLAN.md §12): a call that cannot be made leaves
the layer ``available=False`` with a deterministic reason — the map keeps the
pins and the scout radius — and a failed polygons call degrades to cells with
a warning.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from karum_service_taste.qloo.client import QlooClient
from karum_service_taste.qloo.errors import ErrorCode, QlooError
from karum_service_taste.qloo.models import CallRecord, LocalityRow
from karum_service_taste.taste.derived import haversine_meters
from karum_service_taste.taste.schemas import (
    EntityRefOut,
    GeoPointOut,
    HeatmapCellOut,
    HeatmapResult,
    LocalityPolygonOut,
)
from karum_service_taste.taste.scoring import dedupe_warnings, format_warning

#: The heatmap recordings ran at take=50; the value never truncates cells.
HEATMAP_TAKE = 50

#: How many corridors the brief names from the polygons.
CORRIDOR_LIMIT = 5

#: How many anchor neighbours the map labels by default.
ANCHOR_LIMIT = 3

#: The innermost WKT parenthesised groups: outer rings and holes alike.
_RING_RE = re.compile(r"\(([^()]+)\)")

#: Localities without an area boundary arrive as a single WKT point.
_POINT_RE = re.compile(r"^POINT\s*\(\s*([-\d.eE+]+)\s+([-\d.eE+]+)\s*\)\s*$")


@dataclass(frozen=True)
class AnchorPlace:
    """A place the run already ranked, positioned for corridor anchoring."""

    entity: EntityRefOut
    lat: float
    lon: float


@dataclass(frozen=True)
class _ParsedLocality:
    """One locality row with its main ring parsed and its centroid computed."""

    name: str
    disambiguation: str | None
    affinity: float | None
    lat: float
    lon: float
    ring: list[tuple[float, float]]


async def locality_heatmap(
    client: QlooClient,
    seed: Sequence[EntityRefOut],
    *,
    location: tuple[float, float],
    radius_meters: int,
    include_localities: bool = False,
    corridor_limit: int = CORRIDOR_LIMIT,
    anchor_places: Sequence[AnchorPlace] = (),
    anchor_limit: int = ANCHOR_LIMIT,
    take: int = HEATMAP_TAKE,
) -> HeatmapResult:
    """Cells for the seed at the preset radius, plus corridors when asked."""
    if not seed:
        return HeatmapResult(
            available=False,
            unavailable_reason="seed is empty",
            error_code=ErrorCode.VALIDATION,
            error_message="seed is empty",
        )
    if radius_meters <= 0:
        message = "radius_meters must be positive: a point without a radius returns zero rows"
        return HeatmapResult(
            available=False,
            unavailable_reason=message,
            error_code=ErrorCode.VALIDATION,
            error_message=message,
        )

    entities = [entry.id for entry in seed]
    evidence: list[CallRecord] = []
    warnings: list[str] = []

    try:
        cells_response = await client.insights_heatmap(
            entities, location=location, radius_m=radius_meters, take=take
        )
    except QlooError as exc:
        reason = f"heatmap unavailable ({type(exc).__name__}); showing pins and the scout radius"
        return HeatmapResult(
            available=False,
            unavailable_reason=reason,
            warnings=[reason],
            error_code=exc.error_code,
            error_message=reason,
        )
    if cells_response.call is not None:
        evidence.append(cells_response.call)
    warnings.extend(format_warning(warning) for warning in cells_response.warnings)

    cells = [
        HeatmapCellOut(
            location=(
                GeoPointOut(lat=row.location.lat, lon=row.location.lon)
                if row.location is not None
                else None
            ),
            geohash=row.geohash,
            affinity=row.affinity,
            affinity_rank=row.affinity_rank,
            popularity=row.popularity,
        )
        for row in cells_response.rows
    ]
    if not cells:
        reason = "no heatmap cells matched the seed"
        return HeatmapResult(
            available=False,
            unavailable_reason=reason,
            warnings=dedupe_warnings(warnings),
            error_code=ErrorCode.EMPTY,
            error_message=reason,
            evidence=evidence,
        )

    localities: list[LocalityPolygonOut] = []
    corridors: list[str] = []
    anchors: list[EntityRefOut] = []
    if include_localities:
        try:
            locality_response = await client.insights_localities(
                entities, location=location, radius_m=radius_meters, take=take
            )
        except QlooError as exc:
            warnings.append(
                f"locality polygons unavailable ({type(exc).__name__}); corridors stay unnamed"
            )
        else:
            if locality_response.call is not None:
                evidence.append(locality_response.call)
            warnings.extend(format_warning(warning) for warning in locality_response.warnings)
            parsed: list[_ParsedLocality] = []
            for row in locality_response.rows:
                item = _parse_locality(row)
                if item is None:
                    warnings.append(f"locality {row.name} carried an unreadable boundary")
                    continue
                parsed.append(item)
            localities = [_locality_out(item) for item in parsed]
            if not localities:
                warnings.append("no locality polygons matched the seed; corridors stay unnamed")
            picked = _pick_corridors(
                parsed, location=location, radius_meters=radius_meters, limit=corridor_limit
            )
            corridors = [item.name for item in picked]
            anchors = _anchor_entities(anchor_places, picked, limit=anchor_limit)

    return HeatmapResult(
        cells=cells,
        localities=localities,
        corridors=corridors,
        anchors=anchors,
        available=True,
        warnings=dedupe_warnings(warnings),
        error_code=ErrorCode.UNSPECIFIED,
        evidence=evidence,
    )


def _wkt_rings(text: str | None) -> list[list[tuple[float, float]]]:
    """The polygon rings of a WKT string, ``(lon, lat)`` pairs in file order."""
    if not text:
        return []
    rings: list[list[tuple[float, float]]] = []
    for group in _RING_RE.findall(text):
        points: list[tuple[float, float]] = []
        for pair in group.split(","):
            fields = pair.strip().split()
            if len(fields) < 2:
                points = []
                break
            try:
                points.append((float(fields[0]), float(fields[1])))
            except ValueError:
                points = []
                break
        if len(points) >= 3:
            rings.append(points)
    return rings


def _ring_area_centroid(ring: Sequence[tuple[float, float]]) -> tuple[float, float, float]:
    """Shoelace area and centroid of one ring: ``(area2, lat, lon)``."""
    area2 = 0.0
    cx = 0.0
    cy = 0.0
    count = len(ring)
    for index in range(count):
        x0, y0 = ring[index]
        x1, y1 = ring[(index + 1) % count]
        cross = x0 * y1 - x1 * y0
        area2 += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    if abs(area2) < 1e-12:
        return 0.0, sum(p[1] for p in ring) / count, sum(p[0] for p in ring) / count
    return area2, cy / (3 * area2), cx / (3 * area2)


def _parse_locality(row: LocalityRow) -> _ParsedLocality | None:
    """The main (largest) ring of a locality row with its area centroid."""
    point = _POINT_RE.match(row.boundary.strip()) if row.boundary else None
    if point is not None:
        lon = float(point.group(1))
        lat = float(point.group(2))
        return _ParsedLocality(
            name=row.name,
            disambiguation=row.disambiguation,
            affinity=row.affinity,
            lat=lat,
            lon=lon,
            ring=[(lon, lat)],
        )
    rings = _wkt_rings(row.boundary)
    if not rings:
        return None
    main = max(rings, key=lambda ring: abs(_ring_area_centroid(ring)[0]))
    _, lat, lon = _ring_area_centroid(main)
    return _ParsedLocality(
        name=row.name,
        disambiguation=row.disambiguation,
        affinity=row.affinity,
        lat=lat,
        lon=lon,
        ring=main,
    )


def _locality_out(item: _ParsedLocality) -> LocalityPolygonOut:
    """One parsed locality as the polygon layer consumes it."""
    return LocalityPolygonOut(
        name=item.name,
        disambiguation=item.disambiguation,
        affinity=item.affinity,
        centroid=GeoPointOut(lat=item.lat, lon=item.lon),
        polygon=(
            [GeoPointOut(lat=lat, lon=lon) for lon, lat in item.ring] if len(item.ring) >= 3 else []
        ),
    )


def _pick_corridors(
    parsed: Sequence[_ParsedLocality],
    *,
    location: tuple[float, float],
    radius_meters: int,
    limit: int,
) -> list[_ParsedLocality]:
    """The strongest localities that can serve as corridors, aliases collapsed."""
    picked: list[_ParsedLocality] = []
    seen_names: set[str] = set()
    seen_rings: set[tuple[tuple[float, float], ...]] = set()
    for item in sorted(parsed, key=lambda entry: -(entry.affinity or 0.0)):
        if len(picked) >= limit:
            break
        if item.name in seen_names:
            continue
        shape = tuple(item.ring)
        if shape in seen_rings:
            continue
        if haversine_meters((item.lat, item.lon), location) > radius_meters:
            continue
        seen_names.add(item.name)
        seen_rings.add(shape)
        picked.append(item)
    return picked


def _point_in_ring(ring: Sequence[tuple[float, float]], lat: float, lon: float) -> bool:
    """Even-odd ray casting against a ``(lon, lat)`` ring."""
    inside = False
    count = len(ring)
    for index in range(count):
        x0, y0 = ring[index]
        x1, y1 = ring[(index + 1) % count]
        if (y0 > lat) != (y1 > lat):
            crossing = (x1 - x0) * (lat - y0) / (y1 - y0) + x0
            if lon < crossing:
                inside = not inside
    return inside


def _anchor_entities(
    places: Sequence[AnchorPlace],
    corridors: Sequence[_ParsedLocality],
    *,
    limit: int,
) -> list[EntityRefOut]:
    """The strongest supplied places that fall inside the named corridors."""
    anchors: list[EntityRefOut] = []
    seen: set[str] = set()
    for place in places:
        if len(anchors) >= limit:
            break
        if place.entity.id in seen:
            continue
        if any(_point_in_ring(item.ring, place.lat, place.lon) for item in corridors):
            seen.add(place.entity.id)
            anchors.append(place.entity)
    return anchors
