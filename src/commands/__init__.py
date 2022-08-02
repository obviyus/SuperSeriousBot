"""
Commands for general use.
"""
from telegram import MessageEntity
from telegram.constants import ChatAction
from telegram.ext import CommandHandler

import management
from config.options import config
from management import *
from .animals import animal
from .book import book
from .calc import calc
from .define import define
from .dl import downloader
from .gif import gif
from .hltb import hltb
from .insult import insult
from .joke import joke
from .meme import meme
from .person import person
from .pic import pic, worker_image_seeder
from .ping import ping
from .quote import add_quote, get_quote
from .randdit import nsfw, randdit, worker_seed_posts
from .reddit_comment import get_top_comment
from .sed import sed
from .spurdo import spurdo
from .store import get_object, set_object
from .subscribe import *
from .tldr import tldr
from .translate import translate, tts
from .tv import *
from .ud import ud
from .uwu import uwu
from .vision import age, caption
from .weather import weather


async def disabled(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Disabled command handler.
    """
    await update.message.reply_text("❌ This command is disabled.")


list_of_commands = [
    add_quote,
    add_quote,
    age,
    animal,
    book,
    calc,
    caption,
    define,
    downloader,
    get_chat_stats,
    get_command_stats,
    get_last_seen,
    get_object,
    get_quote,
    get_top_comment,
    get_total_chat_stats,
    get_total_chats,
    get_total_users,
    get_uptime,
    gif,
    hltb,
    insult,
    joke,
    meme,
    nsfw,
    person,
    pic,
    ping,
    randdit,
    set_object,
    spurdo,
    subscribe_reddit,
    tldr,
    translate,
    tts,
    tv,
    ud,
    uwu,
    weather,
]

command_handler_list = []
command_doc_list = {}
for command in list_of_commands:
    if hasattr(command, "api_key"):
        if command.api_key in config["API"]:
            handler = command
        else:
            handler = disabled
    else:
        handler = command

    command_handler_list.append(
        CommandHandler(
            command.triggers,
            handler,
        )
    )

    for trigger in command.triggers:
        command_doc_list[trigger] = {
            "description": command.description,
            "usage": command.usage,
            "example": command.example,
        }

print(command_doc_list)


async def button_handler(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    if query.data.startswith("remove_tv_show"):
        await tv_show_button(update, context)
    elif query.data.startswith("unsubscribe_reddit"):
        await reddit_subscription_button_handler(update, context)


async def usage_string(message: Message, func) -> None:
    """
    Return the usage string for a command.
    """
    await message.reply_text(
        f"{func.description}\n\n<b>Usage:</b>\n<pre>{func.usage}</pre>\n\n<b>Example:</b>\n<pre>{func.example}</pre>",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def increment_command_count(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Increment command count for a /<command> invocation.
    """
    if not update.message:
        return

    await management.increment(update, context)
    sent_command = next(
        iter(update.message.parse_entities([MessageEntity.BOT_COMMAND]).values()), None
    )

    if not sent_command:
        return

    if "@" in sent_command:
        sent_command = sent_command[: sent_command.index("@")]
    sent_command = sent_command[1:]

    logger.info("/{} was used by @{}".format(sent_command, update.message.from_user.id))
    if sent_command not in command_doc_list:
        return

    await update.message.reply_chat_action(ChatAction.TYPING)

    cursor = sqlite_conn.cursor()
    cursor.execute(
        """
        INSERT INTO command_stats (command, user_id) VALUES (?, ?);
        """,
        (sent_command, update.message.from_user.id),
    )
