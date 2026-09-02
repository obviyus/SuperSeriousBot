<p align="center">
  <img src="assets/logo.png" alt="SuperSeriousBot" width="200">
</p>

<h1 align="center">SuperSeriousBot</h1>

<p align="center">A Telegram group bot built with TypeScript, Bun, Effect, and Telly.</p>

SuperSeriousBot has grown with its groups for years. It combines AI, media, search, reminders, social tools, and group history in one bot.

## Features

- AI: native rich replies, semantic search, image and video generation, custom songs, summaries, and transcription
- Group memory: semantic `/search`, citations, member personas, and group lore
- Media: `/set`, `/get`, `/dl`, automatic reel downloads, memes, and quotes
- Social: `/summon`, `/habit`, `/highlight`, reactions, mentions, and `sed` corrections
- Utilities: reminders, scheduled AI tasks, football alerts, weather, books, games, and translation
- Operations: durable Telly inboxes and jobs, polling or webhooks, command quotas, and failure records

Run `/help` to see the commands enabled by the configured API keys.

## Run locally

Requirements:

- Bun 1.4
- `ffmpeg`
- `yt-dlp`

```bash
git clone https://github.com/obviyus/SuperSeriousBot
cd SuperSeriousBot
cp .env.example .env
bun install --frozen-lockfile
bun run dev
```

Required environment values:

- `TELEGRAM_TOKEN`: token from [@BotFather](https://t.me/BotFather)
- `QUOTE_CHANNEL_ID`: private channel used to archive quotes
- `TURSO_DATABASE_URL`: LibSQL or Turso database URL
- `TURSO_AUTH_TOKEN`: database token

Optional integrations:

- `OPENROUTER_API_KEY`: AI, image, video, transcription, summaries, search, and cron
- `OPENROUTER_BASE_URL`: optional OpenRouter-compatible endpoint for local testing
- `KIE_API_KEY`: song generation
- `COBALT_URL`: media downloads
- `NANO_GPT_API_KEY`: URL and YouTube extraction
- `GOODREADS_API_KEY`, `WOLFRAM_APP_ID`, `WEATHERAPI_API_KEY`, and `WAQI_API_KEY`

Operations:

- `ADMINS`: space-separated Telegram user IDs
- `UPDATER`: `polling` or `webhook`
- `WEBHOOK_URL`: public base URL in webhook mode
- `PORT`: webhook server port, default `8443`
- `LOGGING_CHANNEL_ID`: optional Telegram failure log
- `TELLY_STATE_DIRECTORY`: local inbox and job database directory, default `./db`
- `TELEGRAM_API_ROOT`: custom Bot API root for local Test Server harnesses

## Run with Docker

```bash
cp .env.example ssgbot.env
docker compose up --build
```

The image installs `ffmpeg` and `yt-dlp`. The `db` volume stores Telly's durable inbox and scheduled jobs.

## Develop

```bash
bun run check
```

The test suite drives the real Telly handler against its hermetic Bot API fake. It also checks compatibility with the schema produced by all 33 Python migrations.

The local Test Server harness uses leased QA credentials from the Telly skill:

```bash
bun run test:e2e
TELEGRAM_E2E_GROUP=1 bun run test:e2e
TELEGRAM_E2E_WEBHOOK=1 bun run test:e2e
```

Operator commands:

```bash
bun run operator usage --days 30 --status failed
bun run operator search-index --chat-id -1001234567890
bun run operator search-memory --chat-id -1001234567890
```

## Stack

- [Telly](https://github.com/obviyus/telly) owns Telegram transport, updates, routing, persistence, and jobs.
- [Vercel AI SDK](https://ai-sdk.dev) owns text, structured output, streaming, embeddings, images, and video.
- [Effect](https://effect.website) owns typed effects, services, interruption, concurrency, and shutdown.
- [Bun](https://bun.com) owns packages, tests, development, and the production runtime.
- [Turso](https://turso.tech) stores bot and search data.

## Contributing

Use [Angular commit messages](https://github.com/angular/angular/blob/main/CONTRIBUTING.md#-commit-message-format).
