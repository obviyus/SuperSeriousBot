FROM python:3.12-slim AS build

SHELL ["sh", "-exc"]

RUN apt-get update -qy && apt-get install -qyy \
    -o APT::Install-Recommends=false \
    -o APT::Install-Suggests=false \
    curl \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    libz-dev \
    ffmpeg \
    git

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=python3.12 \
    UV_PROJECT_ENVIRONMENT=/app

COPY pyproject.toml /_lock/
COPY uv.lock /_lock/

RUN --mount=type=cache,target=/root/.cache \
    cd /_lock && \
    uv sync --locked --no-dev --no-install-project

COPY . /code
RUN --mount=type=cache,target=/root/.cache \
    uv pip install --python=$UV_PROJECT_ENVIRONMENT --no-deps /code

FROM build AS runtime

WORKDIR /code

RUN groupadd -r app && useradd -r -d /code -g app -N app

RUN apt-get update -qy && apt-get install -qyy \
    -o APT::Install-Recommends=false \
    -o APT::Install-Suggests=false \
    dumb-init \
    sqlite3

COPY --from=build --chown=app:app /code /code

ENTRYPOINT ["dumb-init", "--", "uv", "run"]
CMD ["python", "src/main.py"]

LABEL org.opencontainers.image.source="https://github.com/obviyus/SuperSeriousBot"
