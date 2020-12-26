# Super Serious Bot [![Build Status](https://travis-ci.com/Super-Serious/bot.svg?branch=master)](https://travis-ci.com/Super-Serious/bot)

## Introduction
The Super Serious Bot is a modular, highly-configurable, plug and play Telegram bot built using the fantastic [`python-telegram-bot`](https://github.com/python-telegram-bot/python-telegram-bot) library.

## Features

The Super Serious Bot has a growing set of (simple) functions. Notable ones inclue:
- `/stats` to display today's chat statistics
- `/ban` and `\kick` to ban or kick a member 
- `/weather` to return live weather of a location
- `/tts` to generate speech from provided text using Google's TTS engine
- `/translate` to translate a text in and to any language
- `/ud` to query Urban Dictionary for word definition
- `/hltb` to query HowLongToBeat for a game's data
- `/calc` to query Wolframalpha
... and many more!

## Installation
You can install from source with:
```bash
$ git clone https://github.com/Super-Serious/bot
$ cd bot
$ pip3 install -r requirements.txt
```

## Getting Started

Before you can begin, you'll need to get a token for your bot. You can get one from [@BotFather](https://t.me/botfather).

Place your bot token and other tokens in a `config.yaml` in the project root. You can find an `example_config.yaml` file in `bot/configuration`. Alternatively you can use environment variables for each of the fields with the same name.

Besides this the bot uses MySQL for the `/stats` feature. Set up MySQL as you wish and put in the appropriate creds in the config file

### From Source

Make sure either `config.yaml` or environment variables are set up and run the bot with:

```bash
$ python3 main.py
```

### Docker

Use the `Dockerfile` to build an image for the bot. You can use `example-compose.yaml` as a reference for docker compose. It uses watchtower to update the image from DockerHub and another container for the MySQL DB.

The config for the docker image uses environment variables in a file called `ssgbot.env` you can find the example env_file in `configuration/example.env`

Run with docker-compose as:
```bash
$ docker-compose up -df example-compose.yaml
```

To test if the bot is running, simply send a `/start` message to it.

## Recommended Reading

- [Telegram API documentation](https://core.telegram.org/bots/api)
- [`python-telegram-bot` documentation](https://python-telegram-bot.readthedocs.io/)

## Contributing
Contributions are welcome! You can view our contributing guidelines [here](CONTRIBUTING.md).

Telegram: [@SuperSeriousBot](https://t.me/superseriousbot)
