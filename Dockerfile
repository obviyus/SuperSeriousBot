FROM oven/bun:1.4.0-slim AS dependencies

WORKDIR /app

COPY package.json bun.lock ./
COPY vendor/ ./vendor/

RUN --mount=type=cache,target=/root/.bun/install/cache \
    bun install --frozen-lockfile --production

FROM oven/bun:1.4.0-slim AS runtime

RUN DEBIAN_FRONTEND=noninteractive apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates \
        dumb-init \
        ffmpeg \
        yt-dlp \
    && rm -rf /var/lib/apt/lists/* \
    && install -d -o bun -g bun /app/db

WORKDIR /app

COPY --from=dependencies --chown=bun:bun /app/node_modules ./node_modules
COPY --chown=bun:bun package.json ./
COPY --chown=bun:bun src/ ./src/

USER bun

ENTRYPOINT ["dumb-init", "--"]
CMD ["bun", "src/main.ts"]

LABEL org.opencontainers.image.source="https://github.com/obviyus/SuperSeriousBot"
