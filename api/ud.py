#!/usr/bin/env python
# -*- coding: utf-8 -*-

import emoji
import requests
from telegram import Bot, Update


def ud(bot: Bot, update: Update):
    """
    Command to query UD for word definition
    """
    message = update.message

    # Split after /ud command to get first argument
    word = message.text.strip().split(' ', 1)[1]
    url = f'http://api.urbandictionary.com/v0/define?term={word}'

    res = requests.get(url)
    result = res.json()

    if not result['list']:
        bot.send_message(
            chat_id=message.chat_id,
            text="No entry found.",
            reply_to_message_id=message.message_id,
        )
        return

    # Sort to get result with most thumbs up
    max_thumbs, idx = 0, 0
    for index, value in enumerate(result['list']):
        if max_thumbs < value["thumbs_up"]:
            idx = index
            max_thumbs = value["thumbs_up"]

    result = result['list'][idx]

    heading = result["word"]
    definition = result["definition"]
    example = result["example"]
    thumbs = emoji.emojize(f':thumbs_up: × {max_thumbs}')

    output = f'*{heading}*\n\n{definition}\n\n_{example}_\n\n`{thumbs}`'

    bot.send_message(
        chat_id=message.chat_id,
        text=output,
        reply_to_message_id=message.message_id,
        parse_mode='Markdown',
    )
