FROM python:3.13-alpine AS build

WORKDIR /src

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=python3.13 \
    UV_PROJECT_ENVIRONMENT=/app

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache \
    uv sync --locked --no-dev --no-install-project

COPY src/ ./src/
COPY migrations/ ./migrations/
RUN --mount=type=cache,target=/root/.cache \
    uv pip install --python=$UV_PROJECT_ENVIRONMENT --no-deps .

FROM python:3.13-alpine AS runtime

RUN addgroup -S app && adduser -S -h /app -G app app

RUN apk add --no-cache dumb-init

COPY --from=mwader/static-ffmpeg:latest /ffmpeg /usr/local/bin/
COPY --from=build --chown=app:app /app /app
COPY --from=build --chown=app:app /src/src /src/migrations /app/

RUN mkdir -p /db && chown app:app /db

ENV PATH="/app/bin:$PATH" \
    DATABASE_PATH_PREFIX=/db

WORKDIR /app
USER app

ENTRYPOINT ["dumb-init", "--"]
CMD ["python", "src/main.py"]

LABEL org.opencontainers.image.source="https://github.com/obviyus/SuperSeriousBot"
