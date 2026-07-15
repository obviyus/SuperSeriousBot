FROM python:3.13-slim AS build

WORKDIR /src

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

RUN DEBIAN_FRONTEND=noninteractive apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cargo \
    ca-certificates \
    cmake \
    pkg-config \
    rustc \
    && rm -rf /var/lib/apt/lists/*

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=python3.13 \
    UV_PROJECT_ENVIRONMENT=/app

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache \
    sh -c 'uv sync --locked --no-dev --no-install-project & pid=$!; while kill -0 "$pid" 2>/dev/null; do sleep 10; echo "uv sync still running"; done; wait "$pid"'

COPY src/ ./src/
COPY migrations/ ./migrations/
RUN --mount=type=cache,target=/root/.cache \
    uv pip install --python=$UV_PROJECT_ENVIRONMENT --no-deps .

FROM python:3.13-slim AS runtime

RUN groupadd --system app \
    && useradd --system --home /app --gid app app \
    && install -d -o app -g app /app/db \
    && DEBIAN_FRONTEND=noninteractive apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates \
        dumb-init \
    && rm -rf /var/lib/apt/lists/*

COPY --from=mwader/static-ffmpeg:latest /ffmpeg /usr/local/bin/
COPY --from=build --chown=app:app /app /app
COPY --from=build --chown=app:app /src/src /app/src
COPY --from=build --chown=app:app /src/migrations /app/migrations

ENV PATH="/app/bin:$PATH"

WORKDIR /app
USER app

ENTRYPOINT ["dumb-init", "--"]
CMD ["python", "src/main.py"]

LABEL org.opencontainers.image.source="https://github.com/obviyus/SuperSeriousBot"
