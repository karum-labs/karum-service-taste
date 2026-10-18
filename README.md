# karum-service-taste

The **taste & correlation service** for [Karum](https://github.com/karum-labs/karum-infra#readme). This microservice isolates Qloo's API quirks, authentication, and rate limits from the rest of the system. The Go gateway calls it over gRPC; it resolves entities, maps constraints to tags, fetches block profiles, and scores candidate tenants.

Part of the five-repo Karum layout:

| Repo | Role |
| --- | --- |
| [`karum-infra`](https://github.com/karum-labs/karum-infra) | Shared protos, Docker Compose, Cloud Run manifests |
| [`karum-client`](https://github.com/karum-labs/karum-client) | Flutter UI (web / desktop) |
| [`karum-server`](https://github.com/karum-labs/karum-server) | Go + Gin API gateway |
| **`karum-service-taste`** (this repo) | Qloo integration, caching, taste scoring |
| [`karum-service-ai`](https://github.com/karum-labs/karum-service-ai) | Vertex AI, search grounding, pitch drafting |

## What it does

- **Entity resolution** — turns raw user strings (e.g. "Madre Mezcal") into Qloo Entity IDs.
- **Cross-domain querying** — calls Qloo's recommendation endpoints to fetch places matching a brand in a target city.
- **Data normalization & scoring** — extracts affinity scores, strips extraneous metadata, and flattens cultural tags.
- **Caching** — stores Qloo responses (in Redis or in-process) so repeated runs don't burn through API credits.

The gRPC RPCs (`ResolveEntities`, `ResolveTags`, `GetBlockProfile`, `ScoreCandidates`, plus optional `GetHeatmap` / `CompareSets`) are defined in the shared protos in [`karum-infra`](https://github.com/karum-labs/karum-infra).

## Run path

Requires **Python 3.13+** and [`uv`](https://docs.astral.sh/uv/) (see the version pin in [`karum-infra`](https://github.com/karum-labs/karum-infra)).

```bash
# Install dependencies and run the service.
uv run uvicorn karum_service_taste.main:app --reload --port 8081
```

The service listens on **`:8081`** by default. Confirm it is healthy:

```bash
curl http://localhost:8081/health
```

```json
{
  "service": "service-taste",
  "status": "ok",
  "mode": "fixture",
  "uptime_seconds": 0,
  "time": "2026-10-12T00:00:00+00:00",
  "qloo": {
    "transport": "fixture",
    "metrics": {},
    "rate_limit": null
  }
}
```

Interactive API docs are served at `http://localhost:8081/docs`.

### Configuration

Every setting is read from the environment (optionally via a `.env` file). All values have working defaults, so the service boots in fixture mode with no configuration. The full list is in [`.env.example`](.env.example).

Key variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `TASTE_PORT` | `8081` | HTTP/gRPC listen port |
| `TASTE_MODE` | `fixture` | `live`, `fixture`, or `degraded`; reported on `/health` |
| `TASTE_QLOO_API_KEY` | _(empty)_ | Qloo API key — **never commit** |
| `TASTE_QLOO_BASE_URL` | `https://hackathon.api.qloo.com` | Qloo base URL |
| `TASTE_QLOO_RPS` | `5.0` | Outbound pacing ceiling (observed Qloo limit: 5 rps) |
| `TASTE_FIXTURES_DIR` | `../karum-infra/fixtures` | Redacted fixture pack root used in fixture mode |
| `TASTE_REDIS_ADDR` | `localhost:6379` | Redis cache address (empty ⇒ in-process cache) |
| `TASTE_CACHE_TTL_SECONDS` | `86400` | Cache TTL (24h) |

### Health

`GET /health` reports the service's operational mode:

- `fixture` — replaying recorded payloads, no outbound Qloo calls
- `live` — real Qloo credentials present
- `degraded` — Redis unavailable; running the in-process cache fallback

It also exposes the Qloo client's active transport and call metrics
(calls, errors by code, rows, latency) so the judging dashboard can see what
the service has done without scraping logs.

### Fixtures & offline mode

In `fixture` mode the Qloo client replays the redacted fixture pack shipped by
[`karum-infra`](https://github.com/karum-labs/karum-infra) instead of calling
Qloo — no network, no API spend. The pack holds 76 recordings across the four
judge presets plus the `qloo/misses/` honesty fixtures. The pack root resolves
in order:

1. `TASTE_FIXTURES_DIR`, when set (absolute, or relative to this repo)
2. `../karum-infra/fixtures` — the sibling checkout

A request the pack has not recorded raises `QlooFixtureMissError`: fixture mode
never invents payloads, and every response flows through the same typed
parsers as live mode.

Pack-dependent tests **skip** when the pack is missing locally; CI checks out
`karum-infra` beside this repo and sets `TASTE_REQUIRE_FIXTURES=1`, so a
missing pack fails the build instead of silently skipping.

### Development

```bash
uv run ruff check .    # lint
uv run ruff format .   # format
uv run pytest          # tests, including the full fixture-pack replay
```

### Docker

```bash
docker build -t karum-service-taste .
docker run -p 8081:8081 -e TASTE_QLOO_API_KEY=... karum-service-taste
```

## Repository layout

```
src/karum_service_taste/
  main.py               FastAPI app factory
  api/routes/health.py  GET /health (mode, Qloo transport, metrics)
  core/config.py        environment-driven settings
  core/logging.py       structured logging with secret redaction
  qloo/                 typed Qloo client: endpoints, fixtures, pacing, metrics
tests/                  pytest suite, including the full fixture-pack replay
```

## Ownership

Karum is a two-person build (record: [`DECISIONS.md`](https://github.com/karum-labs/karum-infra/blob/main/DECISIONS.md)). **Side A** owns taste, score, agent, and eval; **side B** owns UI, map, drafts, deploy, and Devpost. This repo is **side A** — the Qloo client, entity and tag resolution, the three-part score, and the cache. Contract changes under `proto/` need a word from side B first.

## Licence

MIT. See [`LICENSE`](LICENSE).
