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

# Debian's yt-dlp lags upstream by months, and sites break old extractors.
# CI passes the current release tag, so a new yt-dlp release changes this
# layer and invalidates the build cache; a daily scheduled build picks new
# releases up and Watchtower deploys them. The zipapp runs on Debian's python3
# for every architecture; the PyInstaller aarch64 build hung CI.
ARG YTDLP_VERSION=latest
RUN timeout 300 bun -e "const v = process.argv[1]; const u = v === 'latest' ? 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp' : 'https://github.com/yt-dlp/yt-dlp/releases/download/' + v + '/yt-dlp'; const r = await fetch(u, { signal: AbortSignal.timeout(240_000) }); if (!r.ok) throw new Error('yt-dlp download failed: ' + r.status); await Bun.write('/usr/local/bin/yt-dlp', r);" "$YTDLP_VERSION" \
    && chmod 755 /usr/local/bin/yt-dlp \
    && installed="$(timeout 60 yt-dlp --version)" \
    && echo "yt-dlp $installed" \
    && { [ "$YTDLP_VERSION" = latest ] || [ "$installed" = "$YTDLP_VERSION" ]; }
LABEL org.obviyus.superseriousbot.yt-dlp="${YTDLP_VERSION}"

WORKDIR /app

COPY --from=dependencies --chown=bun:bun /app/node_modules ./node_modules
COPY --chown=bun:bun package.json ./
COPY --chown=bun:bun src/ ./src/

USER bun

ENTRYPOINT ["dumb-init", "--"]
CMD ["bun", "src/main.ts"]

LABEL org.opencontainers.image.source="https://github.com/obviyus/SuperSeriousBot"
