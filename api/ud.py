#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import json
from requests.models import Response
from telegram import Bot, Update


def ud(bot: Bot, update: Update):
    """
    Command to query UD for word definition
    """
    message = update.message.text

    # Split after /ud command to get first argument
    word = message.text.strip().split(' ', 1)
    url = "http://api.urbandictionary.com/v0/define?term=flump" + word

    res = requests.get(url)
    result = res.json()

    if result is None:
        bot.send_message(
            chat_id=message.chat_id,
            text="No entry found.",
            reply_to_message_id=message.message_id,
        )
        return

    result = result.sort()[0]

    heading = result["word"]
    definition = result["definition"]
    example = result["example"]

    output = '*{heading}* \n {definition} \n {example}'

    bot.send_message(
        chat_id=message.chat_id,
        text=output,
        reply_to_message_id=message.message_id,
        parse_mode='Markdown',
    )
