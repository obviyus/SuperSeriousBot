# Super Serious Bot

[![Release](https://github.com/obviyus/SuperSeriousBot/actions/workflows/release.yml/badge.svg)](https://github.com/obviyus/SuperSeriousBot/actions/workflows/release.yml)
![Lines of Code](https://img.shields.io/tokei/lines/github/obviyus/SuperSeriousBot)
![Commit activity](https://img.shields.io/github/commit-activity/m/obviyus/SuperSeriousBot)
[![Telegram](https://img.shields.io/badge/Telegram-%40SuperSeriousBot-blue)](https://t.me/superseriousbot)

## Introduction

The Super Serious Bot is a modular, asynchronous, highly-configurable, plug and play Telegram bot built using the
fantastic [`python-telegram-bot`](https://github.com/python-telegram-bot/python-telegram-bot) library.

## Features

By adding this bot to your group you can use this growing set of functions. Notable ones include:

- `/stats` to display today's chat statistics
- `/steamstats` to query a user's Steam profile
- `/ban` and `/kick` to ban or kick a member
- `/weather` to return live weather data of a location
- `/tts` to generate speech from provided text using Google's TTS engine
- `/translate` to translate a text in and to any language
- `/hltb` to query the HowLongToBeat API for game data
- `/calc` to query Wolframalpha

... and many more! To see a complete list of commands send `/help` to [@SuperSeriousBot](https://t.me/superseriousbot)

## Usage

### Configuration

0. Before you can begin, you'll need to get a token and API keys for your bot. You can get the token
   from [@BotFather](https://t.me/botfather).
1. Run the following command to generate an empty environment file:

```bash
$ git clone https://github.com/obviyus/SuperSeriousBot
$ cp /bot/configuration/.env.example /bot/ssgbot.env
```

2. Now fill up the `.env` file with all the API keys mentioned

### Running

SuperSeriousBot is run via Docker. The latest image can always be found at: http://ghcr.io/obviyus/SuperSeriousBot.

To start the bot you only need the `docker-compose.yml` and a valid `ssgbot.env` file.

```bash
$ docker-compose --profile prod up -d
```

## Development

We also use Docker as the preferred development environment:

```bash
$ git clone https://github.com/obviyus/SuperSeriousBot
$ cd bot
$ docker-compose --profile dev up
```

Any changes to the code persist through container restarts, no need to rebuild the image!

To test if the bot is running, simply send a `/start` message to it.

## Recommended Reading

- [Telegram API documentation](https://core.telegram.org/bots/api)
- [`python-telegram-bot` documentation](https://python-telegram-bot.readthedocs.io/)

## Contributing

This repository uses the automated [`semantic-release`](https://github.com/semantic-release/semantic-release) suite of tools to generate version numbers. All commit messages **must** conform to the [Angular Commit Message conventions](https://github.com/angular/angular/blob/master/CONTRIBUTING.md#-commit-message-format).
