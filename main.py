import logging

from telegram import ParseMode
from telegram.ext import (Updater, CommandHandler, MessageHandler, Defaults, Filters)

import api
import chat_management
from configuration import config

import datetime


def start(update, context):
    """Start bot"""
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Hi."
    )


def help_cmd(update, context):
    """Show list of commands"""
    cmds = context.bot.commands

    help_text = "*Commands for Super Serious Bot:\n*Send a command with no arguments to get its usage\n\n"
    help_text += ''.join(sorted(f"/{cmd}: {desc}\n\n" for cmd, desc in cmds))

    if not update.effective_chat.type == "private":
        update.message.reply_text("Message sent in DM")

    update.message.from_user.send_message(help_text)


commands = {
    # "command": function
    "ban": chat_management.ban,
    "calc": api.calc,
    "cat": api.cat,
    "catfact": api.catfact,
    "convert": api.currency,
    "countdown": api.countdown,
    "fox": api.fox,
    "gr": api.goodreads,
    "help": help_cmd,
    "hltb": api.hltb,
    "hug": api.hug,
    "insult": api.insult,
    "jogi": api.jogi,
    "joke": api.joke,
    "kick": chat_management.kick,
    "pat": api.pat,
    "pic": api.pic,
    "pfp": api.pad_image,
    "qr": api.make,
    "shiba": api.shiba,
    "spurdo": api.spurdo,
    "start": start,
    "stats": api.stats,
    "time": api.time,
    "tl": api.translate,
    "tts": api.tts,
    "ud": api.ud,
    "weather": api.weather,
    "wink": api.wink,
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
        api.clear, time=datetime.time(18, 30)
    )

    dispatcher.bot.set_my_commands([(cmd, func.__doc__) for cmd, func in commands.items()])

    updater.start_polling(clean=True)
    print("Started bot")
    updater.idle()


if __name__ == '__main__':
    main()
