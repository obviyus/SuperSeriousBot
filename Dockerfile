FROM oven/bun:1.4.0-slim AS dependencies

WORKDIR /app

COPY package.json bun.lock ./
COPY vendor/ ./vendor/

RUN --mount=type=cache,target=/root/.bun/install/cache \
    bun install --frozen-lockfile --production

FROM oven/bun:1.4.0-slim AS runtime

ARG TARGETARCH

RUN DEBIAN_FRONTEND=noninteractive apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates \
        dumb-init \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && install -d -o bun -g bun /app/db

# Debian's yt-dlp lags upstream by months, and Instagram breaks old extractors.
# Fetch the current standalone release on every image build instead.
RUN case "$TARGETARCH" in \
        amd64) asset=yt-dlp_linux ;; \
        arm64) asset=yt-dlp_linux_aarch64 ;; \
        *) echo "unsupported architecture: $TARGETARCH" >&2; exit 1 ;; \
    esac \
    && bun -e "const r = await fetch('https://github.com/yt-dlp/yt-dlp/releases/latest/download/$asset'); if (!r.ok) throw new Error('yt-dlp download failed: ' + r.status); await Bun.write('/usr/local/bin/yt-dlp', r);" \
    && chmod 755 /usr/local/bin/yt-dlp \
    && yt-dlp --version

WORKDIR /app

COPY --from=dependencies --chown=bun:bun /app/node_modules ./node_modules
COPY --chown=bun:bun package.json ./
COPY --chown=bun:bun src/ ./src/

USER bun

ENTRYPOINT ["dumb-init", "--"]
CMD ["bun", "src/main.ts"]

LABEL org.opencontainers.image.source="https://github.com/obviyus/SuperSeriousBot"
