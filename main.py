import datetime
import logging
import traceback
from typing import Callable, Dict, List, TYPE_CHECKING

from telegram import MessageEntity, ParseMode
from telegram.ext import CallbackQueryHandler, CommandHandler, Defaults, Filters, MessageHandler, Updater

import api
import chat_management
import dev
import links
from configuration import config

if TYPE_CHECKING:
    import telegram
    import telegram.ext

# Private channel used for logging exceptions
LOGGING_CHANNEL = -1001543943945


def error_handler(_update: object, context: 'telegram.ext.CallbackContext') -> None:
    """Log the error and send a telegram message to notify the developer."""
    # traceback.format_exception returns the usual python message about an exception, but as a
    # list of strings rather than a single string.
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)

    # Finally, send the message
    try:
        context.bot.send_message(chat_id=LOGGING_CHANNEL, text=f"`{tb_list[-1]}`", parse_mode='Markdown')
    finally:
        raise context.error


def start(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Start bot"""
    if update and update.effective_chat:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Hi."
        )


def help_cmd(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Show list of commands"""
    cmds: List['telegram.BotCommand'] = context.bot.commands

    help_text: str = "*Commands for Super Serious Bot:\n*Send a command with no arguments to get its usage\n\n"
    help_text += ''.join(sorted(f"/{cmd.command}: {cmd.description}\n\n" for cmd in cmds))

    if update.message:
        if update.effective_chat and not update.effective_chat.type == "private":
            update.message.reply_text("Message sent in DM")

        if update.message.from_user:
            update.message.from_user.send_message(help_text)


commands: Dict[str, Callable] = {
    # "command": function
    "age":        api.age,
    "album":      api.album,
    "ban":        chat_management.ban,
    "botstats":   dev.print_botstats,
    "calc":       api.calc,
    "caption":    api.caption,
    "cat":        api.animal,
    "catfact":    api.animal,
    "covid":      api.covid,
    "csgo":       api.csgo,
    "d":          api.define,
    "dice":       api.dice,
    "dl":         links.dl,
    "fox":        api.animal,
    "fw":         api.audio,
    "gif":        api.gif,
    "gr":         api.goodreads,
    "groups":     dev.groups,
    "gstats":     chat_management.print_gstats,
    "help":       help_cmd,
    "hltb":       api.hltb,
    "hug":        api.hug,
    "insult":     api.insult,
    "jogi":       api.audio,
    "joke":       api.joke,
    "kick":       chat_management.kick,
    "pat":        api.pat,
    "pfp":        api.pad_image,
    "pic":        api.pic,
    "pon":        api.audio,
    "search":     api.search,
    "seinfeld":   api.seinfeld,
    "setid":      api.set_steam_id,
    "shiba":      api.animal,
    "spurdo":     api.spurdo,
    "start":      start,
    "stats":      chat_management.print_stats,
    "seen":       chat_management.seen,
    "steamstats": api.steamstats,
    "tl":         api.translate,
    "tldr":       api.tldr,
    "tts":        api.tts,
    "ud":         api.ud,
    "uwu":        api.uwu,
    "wait":       api.wait,
    "weather":    api.weather,
    "wink":       api.wink,
    "wmark":      api.wmark,
}


def funcHandler(update: 'telegram.Update', context: 'telegram.ext.CallbackContext'):
    if update.message:
        message: 'telegram.Message' = update.message
    else:
        return

    command: str
    if update.message.text:
        command = list(message.parse_entities([MessageEntity.BOT_COMMAND]).values())[0]
    else:
        return
    command = command.partition('@')[0][1:].lower()

    if command != 'botstats' and command != 'groups':
        commands[command](update, context)
    else:
        if message.from_user.username in config["AUDIO_RESTORE_USERS"]:
            commands[command](update, context)
        else:
            message.reply_text(text="Unauthorized: You are not one of the developers of SSG Bot.")
    dev.command_increment(command)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    defaults: 'telegram.ext.Defaults' = Defaults(parse_mode=ParseMode.MARKDOWN)
    updater: 'telegram.ext.Updater' = Updater(
        token=config["TELEGRAM_BOT_TOKEN"], defaults=defaults
    )
    dispatcher: 'telegram.ext.Dispatcher' = updater.dispatcher
    job_queue: 'telegram.ext.JobQueue' = updater.job_queue

    for cmd, _ in commands.items():
        dispatcher.add_handler(CommandHandler(cmd, funcHandler, run_async=True))

    # Regex handler
    dispatcher.add_handler(
        MessageHandler(
            Filters.reply & Filters.regex(r"^s\/[\s\S]*\/[\s\S]*"),
            api.sed
        ), group=0
    )

    # Chat message count handler
    dispatcher.add_handler(
        MessageHandler(
            ~Filters.chat_type.private,
            chat_management.increment,
        ), group=1
    )

    # Link handler
    dispatcher.add_handler(
        MessageHandler(
            Filters.text & (Filters.entity(MessageEntity.URL) | Filters.entity(MessageEntity.TEXT_LINK)),
            links.link_handler,
        ), group=3
    )

    dispatcher.add_handler(CallbackQueryHandler(api.search_button))

    # Bot error handler
    dispatcher.add_error_handler(error_handler)

    job_queue.run_daily(
        chat_management.clear, time=datetime.time(18, 30)
    )

    dispatcher.bot.set_my_commands([(cmd, func.__doc__) for cmd, func in commands.items()])

    updater.start_polling(drop_pending_updates=True)
    bot: telegram.Bot = updater.bot
    updater.bot.send_message(
        chat_id=LOGGING_CHANNEL,
        text=f'@{bot.username} started at {datetime.datetime.now()}'
    )
    updater.idle()


if __name__ == '__main__':
    main()
