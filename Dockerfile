# syntax=docker/dockerfile:1

# Use the official uv image to leverage its dependency installer and cache
# mounts for fast, reproducible builds.
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS build

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_EDITABLE=1

WORKDIR /app

# Install dependencies first so this layer caches across source edits.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Copy the rest of the source and install the project itself.
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Runtime stage: slim image without the uv cache or build tooling.
FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Copy the virtualenv produced by the build stage.
COPY --from=build /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# The HTTP port the service listens on. Cloud Run injects its own port; the
# default matches local Compose.
ENV TASTE_PORT=8081
EXPOSE 8081
EXPOSE 9091

# Run as a non-root user.
RUN useradd --create-home --uid 1000 appuser
USER appuser

CMD ["python", "-m", "karum_service_taste"]
