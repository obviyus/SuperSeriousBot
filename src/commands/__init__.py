"""
Commands for general use.
"""

from telegram.ext import CommandHandler

import management
from config.options import config
from main import start
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


command_list = [
    CommandHandler("start", start),
    CommandHandler("stats", management.get_chat_stats),
    CommandHandler("botstats", management.get_command_stats),
    CommandHandler("seen", management.get_last_seen),
    CommandHandler("dl", downloader),
    CommandHandler("c", get_top_comment if "REDDIT" in config["API"] else disabled),
    CommandHandler("users", management.get_total_users),
    CommandHandler("uptime", management.get_uptime),
    CommandHandler("groups", management.get_total_chats),
    CommandHandler("tv", opt_in_tv),
    CommandHandler("cat", animal),
    CommandHandler("shiba", animal),
    CommandHandler("fox", animal),
    CommandHandler("calc", calc if "WOLFRAM_APP_ID" in config["API"] else disabled),
    CommandHandler("d", define),
    CommandHandler("gif", gif if "GIPHY_API_KEY" in config["API"] else disabled),
    CommandHandler("book", book if "GOODREADS_API_KEY" in config["API"] else disabled),
    CommandHandler("hltb", hltb),
    CommandHandler("insult", insult),
    CommandHandler("joke", joke),
    CommandHandler("meme", meme),
    CommandHandler("person", person),
    CommandHandler("pic", pic),
    CommandHandler("r", randdit if "REDDIT" in config["API"] else disabled),
    CommandHandler("nsfw", nsfw if "REDDIT" in config["API"] else disabled),
    CommandHandler("spurdo", spurdo),
    CommandHandler("sub", subscribe_reddit if "REDDIT" in config["API"] else disabled),
    CommandHandler(
        "unsub",
        list_reddit_subscriptions if "REDDIT" in config["API"] else disabled,
    ),
    CommandHandler("tldr", tldr if "SMMRY_API_KEY" in config["API"] else disabled),
    CommandHandler("tl", translate),
    CommandHandler("tts", tts),
    CommandHandler("ud", ud),
    CommandHandler("uwu", uwu),
    CommandHandler("age", age if "AZURE_API_KEY" in config["API"] else disabled),
    CommandHandler(
        "caption",
        caption if "AZURE_API_KEY" in config["API"] else disabled,
    ),
    CommandHandler(["weather", "w"], weather),
    CommandHandler("gstats", management.get_total_chat_stats),
    CommandHandler("set", set_object),
    CommandHandler("get", get_object),
    CommandHandler("addquote", add_quote),
    CommandHandler(["quote", "q"], get_quote),
]


async def button_handler(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    if query.data.startswith("remove_tv_show"):
        await tv_show_button(update, context)
    elif query.data.startswith("unsubscribe_reddit"):
        await reddit_subscription_button_handler(update, context)
