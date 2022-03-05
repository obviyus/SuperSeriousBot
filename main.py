import datetime
import logging
import time
import traceback
from typing import TYPE_CHECKING, Callable, List

from telegram import MessageEntity, ParseMode, ChatAction
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
import dev
import links
from configuration import config
from links.dl import DLBufferUsedWarning

if TYPE_CHECKING:
    import telegram
    import telegram.ext

# Private channel used for logging exceptions
LOGGING_CHANNEL = -1001543943945


class ColorFormatter(logging.Formatter):
    """Formatter to handle colors in logs"""

    def format(self, record):
        format_str = "%(asctime)s - %(color)s(%(filename)s:%(lineno)d) [%(levelname)s] %(message)s%(reset)s"
        reset_color = "\x1b[0m"

        formats = {
            logging.DEBUG: "\x1b[38;21m",  # grey
            logging.TESTING: "\x1b[36;21m",  # cyan
            logging.INFO: "\x1b[34;21m",  # blue
            logging.WARNING: "\x1b[33;21m",  # yellow
            logging.ERROR: "\x1b[31;21m",  # red
            logging.CRITICAL: "\x1b[31;1m",  # bold_red
        }

        # log_fmt = formats[record.levelno] + format_str + reset_color
        log_fmt = format_str.replace("%(color)s", formats[record.levelno]).replace(
            "%(reset)s", reset_color
        )
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


# Add colors to logger
log_handler = logging.StreamHandler()
log_handler.setFormatter(ColorFormatter())

# Add custom logging level
logging.TESTING = 11


def testing(self, message, *args, **kwargs):
    if self.isEnabledFor(logging.TESTING):
        # Yes, logger takes its '*args' as 'args'.
        self._log(logging.TESTING, message, args, **kwargs)


logging.addLevelName(logging.TESTING, "TESTING")
logging.Logger.testing = testing

# Configure logger
logging.basicConfig(
    level=logging.TESTING if config["TESTING"] else logging.INFO,
    format="%(asctime)s - %(name)s:%(levelname)s: %(message)s",
    handlers=[log_handler],
)
log = logging.getLogger()


def error_handler(
        update: "telegram.Update", context: "telegram.ext.CallbackContext"
) -> None:
    """Log the error and send a telegram message to notify the developer."""
    # traceback.format_exception returns the usual python message about an exception, but as a
    # list of strings rather than a single string.
    tb_list = traceback.format_exception(
        None, context.error, context.error.__traceback__
    )

    # Finally, send the message
    if config["TESTING"]:
        raise context.error

    try:
        context.bot.send_message(
            chat_id=LOGGING_CHANNEL, text=f"`{tb_list[-1]}`", parse_mode="Markdown"
        )
        if update.message and not isinstance(context.error, DLBufferUsedWarning):
            update.message.reply_text("An error occurred")
    finally:
        log.error(f"{context.error}")


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


def check_cmd_avail(func: Callable, disabled: bool):
    def wrapped_func(
            update: "telegram.Update", context: "telegram.ext.CallbackContext"
    ):

        message: "telegram.Message" = update.message
        command: str = list(
            message.parse_entities([MessageEntity.BOT_COMMAND]).values()
        )[0]
        command = command.partition("@")[0][1:].lower()

        start = time.time()

        update.message.reply_chat_action(ChatAction.TYPING)
        if disabled:
            update.message.reply_text(
                "This feature is unavailable, please contact the bot admin to enable this."
            )
        elif command not in ["botstats", "groups", "users"]:
            func(update, context)
        elif str(message.from_user.id) in config["DEV_USERNAMES"]:
            func(update, context)
        else:
            message.reply_text(
                text=f"Unauthorized: You are not one of the developers of @{context.bot.username}"
            )

        log_text = " - disabled" if disabled else ""
        log.info(f"[{time.time() - start:.2f}s] - /{command}" + log_text)
        dev.command_increment(command)

    wrapped_func.__doc__ = func.__doc__
    return wrapped_func


class Command:
    """A single command"""

    def __init__(self, cmd: str, func: Callable, keys: List[str] = [], desc: str = ""):
        self.cmd: str = cmd
        self.keys: List[str] = keys
        self.disabled: bool = False
        self.func: Callable
        self.desc: str

        for key in keys:
            if config[key] == "" or config[key] == []:
                self.disabled = True
                log.warning(f"{key} not provided, /{cmd} will be disabled")

        if not self.disabled:
            log.info(f"/{cmd} enabled!")

        self.func = check_cmd_avail(func, self.disabled)

        if self.disabled:
            self.desc = "Disabled command"
        elif desc:
            self.desc = desc
        elif self.func.__doc__:
            self.desc = self.func.__doc__
        else:
            self.desc = "No description"
            log.warning(f"Description not provided for /{cmd}")


commands: List[Command] = [
    # Command(command, func, [keys], desc)
    Command("age", api.age, ["AZURE_KEY"]),
    Command("album", api.album, ["IMGUR_KEY"]),
    Command("ban", chat_management.ban),
    Command("botstats", dev.print_botstats, ["DEV_USERNAMES"]),
    Command("c", links.comment),
    Command("calc", api.calc, ["WOLFRAM_APP_ID"]),
    Command("caption", api.caption, ["AZURE_KEY"]),
    Command("cat", api.animal),
    Command("catfact", api.animal),
    Command("covid", api.covid),
    Command("csgo", api.csgo, ["STEAM_API_KEY"]),
    Command("d", api.define),
    Command("dice", api.dice),
    Command("dl", links.dl),
    Command("fox", api.animal),
    Command("fw", api.audio, ["FOR_WHAT_ID"]),
    Command("gif", api.gif, ["GIPHY_API_KEY"]),
    Command("gr", api.goodreads, ["GOODREADS_API_KEY"]),
    Command("groups", dev.groups, ["DEV_USERNAMES"]),
    Command("gstats", chat_management.print_gstats),
    Command("help", help_cmd),
    Command("hltb", api.hltb),
    Command("hug", api.hug),
    Command("insult", api.insult),
    Command("jogi", api.audio, ["JOGI_FILE_ID"]),
    Command("joke", api.joke),
    Command("kick", chat_management.kick),
    Command("meme", api.meme),
    Command("nsfw", api.nsfw),
    Command("pat", api.pat),
    Command("person", api.person),
    Command("pfp", api.pad_image),
    Command("pic", api.pic),
    Command("pon", api.audio, ["PUNYA_SONG_ID"]),
    Command(
        "r",
        api.randdit,
        ["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USER_AGENT"],
    ),
    Command("rstats", dev.print_reddit_stats),
    Command("seen", chat_management.seen),
    Command(
        "search",
        api.search,
        [
            "PYTHON_QBITTORRENTAPI_HOST",
            "PYTHON_QBITTORRENTAPI_USERNAME",
            "PYTHON_QBITTORRENTAPI_PASSWORD",
        ],
    ),
    Command("setid", api.set_steam_id, ["STEAM_API_KEY"]),
    Command("setw", api.setw),
    Command("shiba", api.animal),
    Command("spurdo", api.spurdo),
    Command("start", start),
    Command("stats", chat_management.print_stats),
    Command("steamstats", api.steamstats, ["STEAM_API_KEY"]),
    Command("sub_reddit", api.subscribe_reddit),
    Command("unsub_reddit", api.unsubscribe_reddit),
    Command("list_reddit", api.list_reddit_subscriptions),
    Command("sub_yt", api.subscribe_youtube),
    Command("unsub_yt", api.unsubscribe_youtube),
    Command("list_yt", api.list_youtube_subscriptions),
    Command("tl", api.translate),
    Command("tldr", api.tldr, ["SMMRY_API_KEY"]),
    Command("tts", api.tts),
    Command("ud", api.ud),
    Command("users", dev.users),
    Command("uwu", api.uwu),
    Command("w", api.weather, ["CLIMACELL_API_KEY"]),
    Command("wait", api.wait),
    Command("weather", api.weather, ["CLIMACELL_API_KEY"]),
    Command("wink", api.wink),
    Command("wmark", api.wmark),
]


def main():
    defaults: "telegram.ext.Defaults" = Defaults(parse_mode=ParseMode.MARKDOWN)
    updater: "telegram.ext.Updater" = Updater(
        token=config["TELEGRAM_BOT_TOKEN"], defaults=defaults
    )
    dispatcher: "telegram.ext.Dispatcher" = updater.dispatcher
    job_queue: "telegram.ext.JobQueue" = updater.job_queue

    # Command handlers
    for cmd in commands:
        dispatcher.add_handler(CommandHandler(cmd.cmd, cmd.func, run_async=True))

    # sed handler
    dispatcher.add_handler(
        MessageHandler(Filters.reply & Filters.regex(r"^s\/[\s\S]*\/[\s\S]*"), api.sed),
        group=0,
    )

    # ping handler
    dispatcher.add_handler(
        MessageHandler(Filters.text & Filters.regex(r"^ping"), api.ping)
    )

    # Chat message count handler
    dispatcher.add_handler(
        MessageHandler(
            ~Filters.chat_type.private,
            chat_management.increment,
        ),
        group=1,
    )

    # Search button handler
    dispatcher.add_handler(CallbackQueryHandler(api.search_button))

    # Bot error handler
    dispatcher.add_error_handler(error_handler)

    # Daily stats clear
    job_queue.run_daily(chat_management.clear, time=datetime.time(18, 30))

    # Deliver Reddit subscriptions
    job_queue.run_daily(api.deliver_reddit_subscriptions, time=datetime.time(17, 30))
    job_queue.run_daily(api.deliver_reddit_subscriptions, time=datetime.time(3, 30))

    # Scan YouTube channels
    job_queue.run_repeating(api.scan_youtube_channels, interval=60, first=0)

    # Set bot commands menu
    dispatcher.bot.set_my_commands([(cmd.cmd, cmd.desc) for cmd in commands])

    # Start seeding random posts
    dispatcher.run_async(api.seed, 10, False)
    dispatcher.run_async(api.seed, 10, True)

    updater.start_polling(drop_pending_updates=True)
    bot: telegram.Bot = updater.bot

    if not config["TESTING"]:
        bot.send_message(
            chat_id=LOGGING_CHANNEL,
            text=f"@{bot.username} started at {datetime.datetime.now()}",
        )
    log.info(f"@{bot.username} started at {datetime.datetime.now()}")

    updater.idle()


if __name__ == "__main__":
    main()
