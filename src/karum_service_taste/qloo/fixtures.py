"""Fixture transport: serve the redacted recordings with zero network.

The pack lives in the infra repo under ``fixtures/`` (QLOO_APIS.md §1): one
JSON envelope per recorded call — 76 of them for the four judge presets — plus
a sha256 manifest that ``make check-fixtures`` verifies in CI.

Fixture mode replays *exactly* those recordings. :class:`FixturePack` indexes
them by canonical request signature
(:func:`karum_service_taste.qloo.canonical.signature`), and a request that
matches nothing raises :class:`QlooFixtureMissError` — fixture mode cannot
invent data, and a miss is a bug (PLAN.md §4).

One exception exists, and it is narrow. The locked presets trim their seed
and candidate lists below what the recordings captured — the Brooklyn session
ran with a fifth signal, the Mumbai one with a fourth — so the preset's
request has no recording of its own. A recording that differs *only* by
carrying more entities answers the same question with a superset of the
signals, and when exactly one such recording exists it is served, with a
warning that names the substitution. Every other parameter — the tag, the
take, the radius, the boundary variant — stays significant, and an ambiguous
replay is still a miss: guessing is not replaying.

Envelope schema (``fixture_version`` 1)::

    {
      "fixture_version": 1,
      "kind": "search" | "insights" | "heatmap" | "locality"
              | "tags" | "demographics" | "compare",
      "source": {"recording", "recorded", "label", "status", "request"},
      "rows": [...],
      "warnings": [...],   # optional
      "note": "..."        # optional
    }

Replay feeds ``rows`` to the same typed models as live traffic
(:mod:`karum_service_taste.qloo.models`); those models accept both the live
nesting and the redacted flattening, so there is one parsing path.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from karum_service_taste.qloo.canonical import RequestSignature, signature
from karum_service_taste.qloo.errors import QlooFixtureError, QlooFixtureMissError
from karum_service_taste.qloo.transport import TransportResponse

#: Schema version carried by every envelope.
FIXTURE_VERSION = 1

#: Directory inside the pack root that holds the recordings.
PACK_SUBDIR = "qloo"

#: The repo root for this checkout (…/karum-service-taste).
REPO_ROOT = Path(__file__).resolve().parents[3]

#: Envelope kinds the pack ships.
KINDS = frozenset({"search", "insights", "heatmap", "locality", "tags", "demographics", "compare"})

#: How each kind nests its rows in a live payload; replay rebuilds this shape.
_CONTAINERS: dict[str, tuple[str, ...]] = {
    "tags": ("results", "tags"),
    "insights": ("results", "entities"),
    "heatmap": ("results", "heatmap"),
    "locality": ("results", "entities"),
    "demographics": ("results", "demographics"),
    "compare": ("results", "a"),
}


def resolve_fixtures_dir(configured: Path) -> Path:
    """Absolute path of the pack; relative settings resolve against the repo root."""
    return configured if configured.is_absolute() else (REPO_ROOT / configured).resolve()


def expected_kinds(path: str, params: Sequence[tuple[str, str]]) -> frozenset[str]:
    """The envelope kinds that may serve this request, derived from the surface."""
    if path in ("/search", "/v2/search"):
        return frozenset({"search"})
    if path == "/v2/tags":
        return frozenset({"tags"})
    if path == "/v2/analysis/compare":
        return frozenset({"compare"})
    if path == "/v2/insights":
        values = dict(params)
        filter_type = values.get("filter.type", "")
        if filter_type == "urn:entity:place":
            return frozenset({"insights"})
        if filter_type == "urn:heatmap":
            if values.get("output.heatmap.boundary") == "urn:entity:locality":
                return frozenset({"locality"})
            return frozenset({"heatmap"})
        if filter_type == "urn:demographics":
            return frozenset({"demographics"})
    return frozenset()


def render_signature(path: str, params: Sequence[tuple[str, str]]) -> str:
    """A readable ``path?k=v&...`` rendering for error messages."""
    if not params:
        return path
    return f"{path}?{'&'.join(f'{name}={value}' for name, value in params)}"


@dataclass(frozen=True)
class FixtureEntry:
    """One indexed recording."""

    path: Path
    kind: str
    request: str
    status: int
    rows: list[Any]
    warnings: list[Any]
    note: str | None = None
    label: str | None = None
    recorded: str | None = None


#: The parameters whose values are comma-separated lists of entity ids.
#:
#: These are the only parameters a trimmed request may differ on: the locked
#: presets carry fewer seed or candidate entities than the recording session
#: did, and the recording answers the same question with a superset of the
#: signals. Every other list parameter — the category tag, the boundary
#: variant — changes what the upstream answers and stays significant.
ENTITY_LIST_PARAMS = frozenset(
    {
        "signal.interests.entities",
        "filter.results.entities",
        "filter.exclude.entities",
        "a.signal.interests.entities",
        "b.signal.interests.entities",
    }
)


@dataclass(frozen=True)
class FixtureMatch:
    """One recording, and what it cost to serve it."""

    entry: FixtureEntry
    #: The entity ids the recording carried that the request left out.
    omitted: tuple[str, ...] = ()

    @property
    def substituted(self) -> bool:
        """Whether the recording answered a wider request than the one asked."""
        return bool(self.omitted)


class FixturePack:
    """The indexed fixture pack: canonical request signature -> recording."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._entries: dict[RequestSignature, FixtureEntry] = {}
        self._duplicates: dict[RequestSignature, list[Path]] = {}
        self._load()

    @property
    def root(self) -> Path:
        """The pack root directory (the one holding ``qloo/``)."""
        return self._root

    @property
    def entries(self) -> dict[RequestSignature, FixtureEntry]:
        """The indexed recordings, keyed by canonical signature."""
        return self._entries

    @property
    def duplicates(self) -> dict[RequestSignature, list[Path]]:
        """Signatures served by more than one file; empty in a healthy pack."""
        return self._duplicates

    def lookup(self, path: str, params: Sequence[tuple[str, str]]) -> FixtureEntry | None:
        """The recording for this exact canonical request, if any."""
        return self._entries.get(signature(path, params))

    def match(self, path: str, params: Sequence[tuple[str, str]]) -> FixtureMatch | None:
        """The recording that answers this request.

        The exact recording wins. When the request has none, a recording that
        differs only by carrying *more* entities is accepted — but only when
        exactly one such recording exists. Two candidates mean the request
        cannot be answered by replay, and a guess is worse than a miss.
        """
        exact = self.lookup(path, params)
        if exact is not None:
            return FixtureMatch(entry=exact)
        wanted = dict(signature(path, params)[1])
        found: list[FixtureMatch] = []
        for entry_signature, entry in self._entries.items():
            if entry_signature[0] != path:
                continue
            recorded = dict(entry_signature[1])
            if set(recorded) != set(wanted):
                continue
            omitted: list[str] = []
            differs = False
            for name, value in wanted.items():
                if name in ENTITY_LIST_PARAMS:
                    asked = tuple(value)
                    have = tuple(recorded[name])
                    if not set(asked).issubset(have):
                        differs = True
                        break
                    omitted.extend(part for part in have if part not in asked)
                elif recorded[name] != value:
                    differs = True
                    break
            if differs:
                continue
            found.append(FixtureMatch(entry=entry, omitted=tuple(sorted(omitted))))
        if len(found) != 1:
            return None
        return found[0]

    def _load(self) -> None:
        base = self._root / PACK_SUBDIR
        if not base.is_dir():
            raise QlooFixtureError(
                f"fixture pack not found at {base}; check out karum-infra next to "
                "this repo or set TASTE_FIXTURES_DIR"
            )
        for file in sorted(base.rglob("*.json")):
            entry = self._read_entry(file)
            key = signature(entry.request)
            if key in self._entries:
                self._duplicates.setdefault(key, [self._entries[key].path]).append(file)
                continue
            self._entries[key] = entry

    @staticmethod
    def _read_entry(file: Path) -> FixtureEntry:
        try:
            document = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise QlooFixtureError(f"fixture {file} is unreadable: {exc}") from exc
        if not isinstance(document, dict):
            raise QlooFixtureError(f"fixture {file} is not an envelope object")
        if document.get("fixture_version") != FIXTURE_VERSION:
            raise QlooFixtureError(
                f"fixture {file} has version {document.get('fixture_version')!r}, "
                f"expected {FIXTURE_VERSION}"
            )
        kind = document.get("kind")
        if kind not in KINDS:
            raise QlooFixtureError(f"fixture {file} has unknown kind {kind!r}")
        source = document.get("source") or {}
        request = source.get("request")
        if not isinstance(request, str) or not request:
            raise QlooFixtureError(f"fixture {file} has no source.request")
        rows = document.get("rows")
        if not isinstance(rows, list):
            raise QlooFixtureError(f"fixture {file} has no rows list")
        warnings = document.get("warnings")
        status = source.get("status")
        return FixtureEntry(
            path=file,
            kind=str(kind),
            request=request,
            status=int(status) if isinstance(status, int) else 200,
            rows=rows,
            warnings=warnings if isinstance(warnings, list) else [],
            note=document.get("note"),
            label=source.get("label"),
            recorded=source.get("recorded"),
        )


def reconstruct_payload(kind: str, rows: list[Any], warnings: list[Any]) -> dict[str, Any]:
    """Rebuild the live payload nesting around redacted rows for replay."""
    payload: dict[str, Any] = {"success": True}
    if kind == "search":
        # Live /search publishes results as the list itself.
        payload["results"] = rows
    elif kind == "compare":
        # The recordings carry side A's rows; B and the shared matches were
        # empty (the redactor keeps every list it finds, so this is faithful).
        payload["results"] = {"a": rows, "b": [], "matchEntities": [], "tags": []}
    else:
        container = _CONTAINERS[kind]
        node: dict[str, Any] = {}
        cursor = node
        for part in container[:-1]:
            cursor[part] = {}
            cursor = cursor[part]
        cursor[container[-1]] = rows
        payload.update(node)
    if warnings:
        payload["warnings"] = warnings
    return payload


class FixtureTransport:
    """Serves the pack with no network; a miss is an error, not a fallback."""

    name = "fixture"

    def __init__(self, pack: FixturePack) -> None:
        self._pack = pack

    @property
    def pack(self) -> FixturePack:
        """The underlying pack, for health reporting and tests."""
        return self._pack

    async def get(self, path: str, params: Sequence[tuple[str, str]]) -> TransportResponse:
        match = self._pack.match(path, params)
        if match is None:
            missing = render_signature(path, params)
            raise QlooFixtureMissError(
                f"fixture mode has no recording for {missing!r}; the pack at "
                f"{self._pack.root} holds {len(self._pack.entries)} recordings"
            )
        entry = match.entry
        allowed = expected_kinds(path, params)
        if allowed and entry.kind not in allowed:
            raise QlooFixtureError(
                f"fixture {entry.path.name} is kind {entry.kind!r} but the request "
                f"is {sorted(allowed)}"
            )
        warnings = list(entry.warnings)
        if match.substituted:
            # The recording answered a wider request than the one asked. Say so
            # in the response, so the run carries the substitution all the way
            # to the operator's warning banner.
            warnings.append(
                {
                    "type": "fixture replay substituted the recorded call",
                    "signal.interests.entities": list(match.omitted),
                }
            )
        payload = reconstruct_payload(entry.kind, entry.rows, warnings)
        return TransportResponse(status=entry.status, headers={}, payload=payload)

    async def aclose(self) -> None:
        """Fixture replay holds no resources."""
        return None
