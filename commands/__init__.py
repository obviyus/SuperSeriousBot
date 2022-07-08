"""
Commands for general use.
"""
from telegram.ext import CommandHandler

import management
from config.options import config
from main import disabled, start
from .animals import animal
from .calc import calc
from .dl import downloader
from .ping import ping
from .reddit_comment import get_top_comment
from .sed import sed
from .tv import *

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
    CommandHandler("calc", calc),
]
