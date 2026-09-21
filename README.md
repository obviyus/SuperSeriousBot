<p align="center">
  <img src="assets/logo.png" alt="SuperSeriousBot" width="200">
</p>

<h1 align="center">SuperSeriousBot</h1>

<p align="center">A Telegram group bot built with TypeScript, Bun, Effect, and Telly.</p>

SuperSeriousBot has grown with its groups for years. It combines AI, media, search, reminders, social tools, and group history in one bot.

## Features

- AI: native rich replies, semantic search, image and video generation, custom songs, summaries, and transcription
- Native Telegram UI: rich tables, lists, details, charts, dates, links, and command dashboards
- Group memory: semantic `/search`, citations, member personas, and group lore
- Media: `/set`, `/get`, `/dl`, automatic reel downloads, memes, and quotes
- Social: `/summon`, `/habit`, `/highlight`, reactions, mentions, and `sed` corrections
- Utilities: reminders, scheduled AI tasks, football alerts, weather, books, games, and translation
- Operations: durable Telly inboxes and jobs, polling or webhooks, command quotas, and failure records

Run `/help` to see the commands enabled by the configured API keys.

`/tl` uses Google Translate's batch web endpoint through `google-translate-api-x`, without an API key. Use `/tl Bonjour` for English, `/tl fr - Good morning` for a specific language, or reply to a message with `/tl [language]`. Provider outages and rate limits are reported separately from unknown languages.

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
- `BASED_PROVIDER`: `local` (default) or `nanogpt` for `/based`
- `BASED_MODEL`: model ID for `/based`
- `BASED_BASE_URL`: OpenAI-compatible endpoint for the `local` provider (include `/v1`)
- `KIE_API_KEY`: song generation
- `COBALT_URL`: media downloads
- `NANO_GPT_API_KEY`: URL/YouTube extraction and `/based` when `BASED_PROVIDER=nanogpt`
- `GOODREADS_API_KEY`, `WOLFRAM_APP_ID`, `WEATHERAPI_API_KEY`, and `WAQI_API_KEY`

`/based [query]` streams a text answer from the configured model. Reply to a
text message to include it as context. It has its own chat/user whitelist and a
40-request daily limit, like `/ask`. Enable it for a group through `/settings`.
It needs no OpenRouter key and does not use `/model ask` or `/thinking` settings.
Admins can use `/model based <model-id>` to save a global model override. `/model`
shows the current selection, and `/model all <model-id>` also includes `/based`.
Changes apply to the next request and survive restarts. `BASED_MODEL` is the default
until an override is saved; `/model` does not change the configured provider.
Set `BASED_PROVIDER=nanogpt` and `BASED_MODEL` to a NanoGPT catalog ID to use hosted
inference. It uses the existing `NANO_GPT_API_KEY` and NanoGPT's fixed API endpoint;
`BASED_BASE_URL` applies only to `local`. NanoGPT requests use `reasoning_effort=none`;
local requests retain their chat-template thinking control.
Use `/ask` for supported images. `/based` rejects media. Requests stop after two minutes; responses
are capped at 1,024 tokens. There is no fallback to another provider on failure.

For the local provider, use a private Tailscale HTTPS route to its loopback listener, as with
Cobalt. Allow only the bot host to reach that route. Keep the endpoint and model ID
in the app environment; do not expose the unauthenticated model API publicly.

Operations:

- `ADMINS`: space-separated Telegram user IDs
- `UPDATER`: `polling` or `webhook`
- `WEBHOOK_URL`: public base URL in webhook mode
- `PORT`: webhook server port, default `8443`
- `LOGGING_CHANNEL_ID`: optional Telegram failure log
- `TELLY_STATE_DIRECTORY`: local inbox and job database directory, default `./db`
- `TELEGRAM_API_ROOT`: custom Bot API root for local Test Server harnesses

Evaluate search with a private JSON file containing `[{ "chatId": -100123, "question": "Who is the biggest tech nerd here?" }]`:

```bash
bun run search:evaluate /path/to/private-questions.json
```

This reads chat data and calls the configured AI service without sending Telegram messages or writing search events. Each answer gets a fresh review against its complete context. Results are printed as JSON lines. Keep question files and reports private.

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
TELEGRAM_E2E_STATIC_RICH=1 TELEGRAM_E2E_GROUP=1 bun run test:e2e
TELEGRAM_E2E_WEBHOOK=1 bun run test:e2e
```

Operator commands:

```bash
bun run operator usage --days 30 --status failed
bun run operator search-index --chat-id -1001234567890
bun run operator search-memory --chat-id -1001234567890
```

Before deploying `/model based` to an existing database, run
`bun run operator migrate-model-settings` with that database's environment. This
adds the nullable model-setting field and preserves existing settings. Run it
separately before replacing the bot.

Before deploying the incremental search indexer to an existing database, run
`bun run operator migrate-query-schema` with that database's environment.
The migration adds the generation column to existing search progress and replaces
the source-change triggers in one transaction. It preserves existing rows and the
previous indexer's append notifications, and is safe to run again. Run it separately
before replacing the running bot; startup does not upgrade existing progress.

Indexing saves progress separately for each chat and embedding configuration.
Unchanged chats do no indexing work. New messages extend the unfinished windows
and speaker groups. Older imports, source edits or deletes, and author changes
request the existing full-history pass. Existing embedding ranges retain their
current reuse behavior. Each pass claims a generation and captures a fixed message
boundary. Later appends remain pending without invalidating that prefix. Backfills,
edits, deletes, author changes, and newer workers invalidate the claim. A failed or
superseded pass cannot advance progress.

## Stack

- [Telly](https://github.com/obviyus/telly) owns Telegram transport, updates, routing, persistence, and jobs.
- [Vercel AI SDK](https://ai-sdk.dev) owns text, structured output, streaming, embeddings, images, and video.
- [Effect](https://effect.website) owns typed effects, services, interruption, concurrency, and shutdown.
- [Bun](https://bun.com) owns packages, tests, development, and the production runtime.
- [Turso](https://turso.tech) stores bot and search data.

## Contributing

Use [Angular commit messages](https://github.com/angular/angular/blob/main/CONTRIBUTING.md#-commit-message-format).
