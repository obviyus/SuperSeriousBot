<p align="center">
    <img src="assets/logo.png" style="background: white; border-radius: 10%; padding: 10px" alt="Logo" width="200px">
</p>

<p align="center">
  <img alt="GitHub commit activity" src="https://img.shields.io/github/commit-activity/m/obviyus/SuperSeriousBot">
  <img alt="Build" src="https://github.com/obviyus/SuperSeriousBot/actions/workflows/release.yml/badge.svg">
  <img alt="Docker Image Size" src="https://ghcr-badge.egpl.dev/obviyus/superseriousbot/size">
</p>
<p align="center">
  <a href="https://github.com/obviyus/SuperSeriousBot/blob/master/LICENSE"><img alt="GitHub license" src="https://img.shields.io/github/license/obviyus/SuperSeriousBot"></a>
  <img alt="GitHub release (latest by date including pre-releases)" src="https://img.shields.io/github/v/release/obviyus/superseriousbot?include_prereleases">
</p>
<p align="center">
   <a href="https://t.me/superseriousbot"><img alt="Telegram Link" src="https://img.shields.io/badge/Telegram-%40SuperSeriousBot-blue"></a>
</p>

<h2 align="center">SuperSeriousBot</h2>
<p align="center">A modular, asynchronous, highly-configurable, plug and play Telegram bot built using the fantastic <a href="https://github.com/python-telegram-bot/python-telegram-bot"><code>python-telegram-bot</code></a> library.</p>

## Introduction

SuperSeriousBot is an asynchronous Telegram bot with modular commands, SQLite-backed state, and API-key-gated optional features.

## ✨ Features

Current command set includes:

- AI features: `/ask`, `/edit`, `/tldr`, `/tr`, `/model`, `/thinking`
- Object store + media: `/set`, `/get`, `/dl`, `/gif`, `/meme`, `/joke`
- Language + utility: `/tl`, `/tts`, `/define`, `/ud`, `/calc`, `/book`
- Group utilities: `/remind`, `/habit`, `/summon`, `/highlight`
- Stats + moderation: `/stats`, `/gstats`, `/ustats`, `/seen`, `/block`, `/unblock`, `/whitelist`
- Social graph: `/friends`
- Weather + quotes: `/weather`, `/addquote`, `/quote`

Notes:

- No standalone caption command. Image captioning is done by replying to an image/sticker with `/ask`.
- Most API-key commands are auto-disabled when keys are missing; some validate at runtime (for example `/weather`).
- Send `/help` to [@SuperSeriousBot](https://t.me/superseriousbot) for the live command list.

## 🏗 Usage

### Configuration

Before you can begin, you'll need to get a token and API keys for your bot. You can get the token from [@BotFather](https://t.me/botfather).

Run the following command to generate an empty environment file:

```bash
$ git clone https://github.com/obviyus/SuperSeriousBot
$ cp .env.example ssgbot.env
```

Fill `ssgbot.env`.

Required:

- `TELEGRAM_TOKEN`
- `QUOTE_CHANNEL_ID`

Optional:

- `OPENROUTER_API_KEY` for `/ask`, `/edit`, `/tldr`, `/tr`
- `WAQI_API_KEY` for `/weather` AQI
- `WEATHERAPI_API_KEY` for `/weather`
- `GIPHY_API_KEY` for `/gif`
- `GOODREADS_API_KEY` for `/book`
- `WOLFRAM_APP_ID` for `/calc`
- `COBALT_URL` for `/dl` backend override
- `ADMINS`, `UPDATER`, `WEBHOOK_URL`, `LOGGING_CHANNEL_ID` for bot ops

### Running

SuperSeriousBot is run via Docker. The latest image can always be found at: `ghcr.io/obviyus/SuperSeriousBot`.

To start the bot you only need `docker-compose.yaml` and a valid `ssgbot.env` file.

```bash
$ docker compose up --build
```

## Development

Local dev (without Docker):

```bash
$ uv sync
$ uv run python src/main.py
```

## Recommended Reading

- [Telegram API documentation](https://core.telegram.org/bots/api)
- [`python-telegram-bot` documentation](https://python-telegram-bot.readthedocs.io/)

## Contributing

All commit messages **must** conform to the [Angular Commit Message conventions](https://github.com/angular/angular/blob/master/CONTRIBUTING.md#-commit-message-format).
