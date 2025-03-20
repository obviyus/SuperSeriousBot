FROM python:3.12-slim AS build

SHELL ["sh", "-exc"]

# Combine RUN commands and cleanup in the same layer
RUN apt-get update -qy && \
    apt-get install -qyy --no-install-recommends \
    curl \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    libz-dev \
    ffmpeg \
    git && \
    rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=python3.12 \
    UV_PROJECT_ENVIRONMENT=/app

# Copy only dependency files first to leverage Docker layer caching
WORKDIR /code
COPY pyproject.toml uv.lock ./

# Install dependencies with better caching
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

# Copy application code
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --python=$UV_PROJECT_ENVIRONMENT --no-deps .

FROM python:3.12-slim AS runtime

WORKDIR /code

RUN groupadd -r app && useradd -r -d /code -g app -N app && \
    apt-get update -qy && \
    apt-get install -qyy --no-install-recommends \
    dumb-init \
    sqlite3 && \
    rm -rf /var/lib/apt/lists/*

COPY --from=build --chown=app:app /app /app
COPY --from=build --chown=app:app /code /code

USER app

ENTRYPOINT ["dumb-init", "--"]
CMD ["python", "src/main.py"]

LABEL org.opencontainers.image.source="https://github.com/obviyus/SuperSeriousBot"
