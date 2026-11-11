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
        python3 \
    && rm -rf /var/lib/apt/lists/* \
    && install -d -o bun -g bun /app/db

# Debian's yt-dlp lags upstream by months, and Instagram breaks old extractors.
# Fetch the current release on every image build instead. The zipapp runs on
# Debian's python3 for every architecture; the PyInstaller aarch64 build hung CI.
RUN timeout 300 bun -e "const r = await fetch('https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp', { signal: AbortSignal.timeout(240_000) }); if (!r.ok) throw new Error('yt-dlp download failed: ' + r.status); await Bun.write('/usr/local/bin/yt-dlp', r);" \
    && chmod 755 /usr/local/bin/yt-dlp \
    && timeout 60 yt-dlp --version

WORKDIR /app

COPY --from=dependencies --chown=bun:bun /app/node_modules ./node_modules
COPY --chown=bun:bun package.json ./
COPY --chown=bun:bun src/ ./src/

USER bun

ENTRYPOINT ["dumb-init", "--"]
CMD ["bun", "src/main.ts"]

LABEL org.opencontainers.image.source="https://github.com/obviyus/SuperSeriousBot"
