import logging

from telegram import ParseMode
from telegram.ext import (Updater, CommandHandler, MessageHandler, Defaults, Filters)

import api
import chat_management
from configuration import config

import datetime


def start(update, context):
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Hi."
    )


commands = {
    # "command": function
    "ban": chat_management.ban,
    "calc": api.calc,
    "countdown": api.countdown,
    "convert": api.currency,
    "hltb": api.hltb,
    "kick": chat_management.kick,
    "start": start,
    "time": api.time,
    "tl": api.translate,
    "tts": api.tts,
    "ud": api.ud,
    "stats": api.stats
}


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    defaults = Defaults(parse_mode=ParseMode.MARKDOWN)
    updater = Updater(
        token=config["TELEGRAM_BOT_TOKEN"], use_context=True, defaults=defaults
        )
    dispatcher = updater.dispatcher
    j = updater.job_queue

    for cmd, func in commands.items():
        dispatcher.add_handler(CommandHandler(cmd, func))

    dispatcher.add_handler(MessageHandler(
        Filters.reply & Filters.regex(r"^s\/[\s\S]*\/[\s\S]*"), api.sed
    ))

    dispatcher.add_handler(MessageHandler(
        Filters.text,
        api.stats_check
    ))

    j.run_daily(
        api.clear, time = datetime.time(hour=5, minute=30, second=0, microsecond=0, tzinfo=None, fold=0)
    )

    updater.start_polling(clean=True)
    print("Started bot")
    updater.idle()


if __name__ == '__main__':
    main()
