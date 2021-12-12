import datetime
import logging
import traceback
from typing import Callable, Dict, List, TYPE_CHECKING

from telegram import MessageEntity, ParseMode
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    Defaults,
    Filters,
    MessageHandler,
    Updater,
)

import api
import chat_management
import time
import dev
import links
from configuration import config

if TYPE_CHECKING:
    import telegram
    import telegram.ext

# Private channel used for logging exceptions
LOGGING_CHANNEL = -1001543943945


def error_handler(_update: object, context: "telegram.ext.CallbackContext") -> None:
    """Log the error and send a telegram message to notify the developer."""
    # traceback.format_exception returns the usual python message about an exception, but as a
    # list of strings rather than a single string.
    tb_list = traceback.format_exception(
        None, context.error, context.error.__traceback__
    )

    # Finally, send the message
    try:
        context.bot.send_message(
            chat_id=LOGGING_CHANNEL, text=f"`{tb_list[-1]}`", parse_mode="Markdown"
        )
    finally:
        logging.error(f"{context.error}")
        raise context.error


def start(update: "telegram.Update", context: "telegram.ext.CallbackContext") -> None:
    """Start bot"""
    if update and update.effective_chat:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"👋 @{update.message.from_user.first_name}",
        )


def help_cmd(
    update: "telegram.Update", context: "telegram.ext.CallbackContext"
) -> None:
    """Show list of commands"""
    cmds: List["telegram.BotCommand"] = context.bot.commands

    help_text: str = (
        f"*Commands for @{context.bot.username}:*\n\nTap on a command to get help.\n\n"
    )
    help_text += "".join(sorted(f"/{cmd.command}: {cmd.description}\n" for cmd in cmds))

    if update.message:
        if update.effective_chat and not update.effective_chat.type == "private":
            update.message.reply_text("Message sent in private.")

        if update.message.from_user:
            update.message.from_user.send_message(help_text)


def check_for_keys(func: Callable, key: str):
    def warn_func(update: "telegram.Update", context: "telegram.ext.CallbackContext"):
        """Disabled command"""
        update.message.reply_text(
            "This feature is unavailable, please contact the bot admin to remedy this."
        )

    if config[key] != "":
        return func
    else:
        return warn_func


commands: Dict[str, Callable] = {
    # "command": function
    "age": check_for_keys(api.age, "AZURE_KEY"),
    "album": check_for_keys(api.album, "IMGUR_KEY"),
    "ban": chat_management.ban,
    "botstats": dev.print_botstats,
    "calc": check_for_keys(api.calc, "WOLFRAM_APP_ID"),
    "caption": check_for_keys(api.caption, "AZURE_KEY"),
    "cat": api.animal,
    "catfact": api.animal,
    "covid": api.covid,
    "csgo": check_for_keys(api.csgo, "STEAM_API_KEY"),
    "d": api.define,
    "dice": api.dice,
    "dl": links.dl,
    "fox": api.animal,
    "fw": check_for_keys(api.audio, "FOR_WHAT_ID"),
    "gif": check_for_keys(api.gif, "GIPHY_API_KEY"),
    "gr": check_for_keys(api.goodreads, "GOODREADS_API_KEY"),
    "groups": dev.groups,
    "gstats": chat_management.print_gstats,
    "help": help_cmd,
    "hltb": api.hltb,
    "hug": api.hug,
    "insult": api.insult,
    "jogi": check_for_keys(api.audio, "JOGI_FILE_ID"),
    "joke": api.joke,
    "kick": chat_management.kick,
    "pat": api.pat,
    "pfp": api.pad_image,
    "pic": api.pic,
    "pon": check_for_keys(api.audio, "PUNYA_SONG_ID"),
    "search": api.search,
    "setid": check_for_keys(api.set_steam_id, "STEAM_API_KEY"),
    "setw": api.setw,
    "shiba": api.animal,
    "spurdo": api.spurdo,
    "start": start,
    "stats": chat_management.print_stats,
    "seen": chat_management.seen,
    "steamstats": check_for_keys(api.steamstats, "STEAM_API_KEY"),
    "tl": api.translate,
    "tldr": check_for_keys(api.tldr, "SMMRY_API_KEY"),
    "tts": api.tts,
    "ud": api.ud,
    "uwu": api.uwu,
    "w": check_for_keys(api.weather, "CLIMACELL_API_KEY"),
    "wait": api.wait,
    "weather": check_for_keys(api.weather, "CLIMACELL_API_KEY"),
    "wink": api.wink,
    "wmark": api.wmark,
}


def funcHandler(update: "telegram.Update", context: "telegram.ext.CallbackContext"):
    if update.message:
        message: "telegram.Message" = update.message
    else:
        return

    command: str
    if update.message.text:
        command = list(message.parse_entities([MessageEntity.BOT_COMMAND]).values())[0]
    else:
        return
    command = command.partition("@")[0][1:].lower()

    start = time.time()
    if command != "botstats" and command != "groups":
        commands[command](update, context)
    else:
        if message.from_user.username in config["DEV_USERNAMES"]:
            commands[command](update, context)
        else:
            message.reply_text(
                text=f"Unauthorized: You are not one of the developers of @{context.bot.username}"
            )

    logging.log(logging.INFO, f"[{time.time() - start:.2f}s] - /{command}")
    dev.command_increment(command)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    defaults: "telegram.ext.Defaults" = Defaults(parse_mode=ParseMode.MARKDOWN)
    updater: "telegram.ext.Updater" = Updater(
        token=config["TELEGRAM_BOT_TOKEN"], defaults=defaults
    )
    dispatcher: "telegram.ext.Dispatcher" = updater.dispatcher
    job_queue: "telegram.ext.JobQueue" = updater.job_queue

    for cmd, _ in commands.items():
        dispatcher.add_handler(CommandHandler(cmd, funcHandler, run_async=True))

    # Regex handler
    dispatcher.add_handler(
        MessageHandler(Filters.reply & Filters.regex(r"^s\/[\s\S]*\/[\s\S]*"), api.sed),
        group=0,
    )

    # Chat message count handler
    dispatcher.add_handler(
        MessageHandler(
            ~Filters.chat_type.private,
            chat_management.increment,
        ),
        group=1,
    )

    dispatcher.add_handler(CallbackQueryHandler(api.search_button))

    # Bot error handler
    dispatcher.add_error_handler(error_handler)

    for k, v in config.items():
        if v == "":
            logging.warning(
                f"{k} environment variable not provided, the commands that use this will be disabled."
            )

    job_queue.run_daily(chat_management.clear, time=datetime.time(18, 30))

    dispatcher.bot.set_my_commands(
        [(cmd, func.__doc__) for cmd, func in commands.items()]
    )

    updater.start_polling(drop_pending_updates=True)
    bot: telegram.Bot = updater.bot
    updater.bot.send_message(
        chat_id=LOGGING_CHANNEL,
        text=f"@{bot.username} started at {datetime.datetime.now()}",
    )

    updater.idle()


if __name__ == "__main__":
    main()
