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

A recent rewrite has just wrapped up, making SuperSeriousBot completely asynchronous. The rewrite also included:

- a general clean up of all functions
- combining the many different database files into a single SQLite file
- using poetry for dependency management
- warn and disable functions with missing API keys
- improved logging to development channel

## ✨ Features

By adding this bot to your group you can use this growing set of functions. Notable ones include:

- [x] An **object-store** to save any image, video, GIF, audio etc. with a key
- [x] Ask questions with AI and Google search grounding
- [x] Caption images using vision models
- [x] Live weather and predictions for any location
- [x] Generate text-to-speech using Google Text-to-Speech
- [x] Translate a text from any language to any other
- [x] Generate a TLDR of any article
- [x] QuoteDB for adding and retrieving messages
- [x] A social graph of all members in a chat using [`visjs`](https://visjs.org/)

... and many more! To see a complete list of commands send `/help` to [@SuperSeriousBot](https://t.me/superseriousbot)

## 🏗 Usage

### Configuration

Before you can begin, you'll need to get a token and API keys for your bot. You can get the token from [@BotFather](https://t.me/botfather).

Run the following command to generate an empty environment file:

```bash
$ git clone https://github.com/obviyus/SuperSeriousBot
$ cp .env.example ssgbot.env
```

2. Now fill up the `.env` file with all the API keys you need. The only mandatory key is the Telegram bot token.

### Running

SuperSeriousBot is run via Docker. The latest image can always be found at: http://ghcr.io/obviyus/SuperSeriousBot.

To start the bot you only need the `docker-compose.yml` and a valid `ssgbot.env` file.

```bash
$ docker-compose up
```

## Development

We also use Docker as the preferred development environment:

```bash
$ docker-compose up
```

Any changes to the code persist through container restarts, no need to rebuild the image for a single change. In the future I may experiment with adding [`nodemon`](https://nodemon.io/) for watching files.

## Recommended Reading

- [Telegram API documentation](https://core.telegram.org/bots/api)
- [`python-telegram-bot` documentation](https://python-telegram-bot.readthedocs.io/)

## Contributing

This repository uses the automated [`semantic-release`](https://github.com/semantic-release/semantic-release) suite of tools to generate version numbers. All commit messages **must** conform to the [Angular Commit Message conventions](https://github.com/angular/angular/blob/master/CONTRIBUTING.md#-commit-message-format).
