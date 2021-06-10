import datetime
import logging
from typing import TYPE_CHECKING, List, Dict, Callable

from telegram import ParseMode, MessageEntity
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, Defaults, Filters

import api
import chat_management
import dev
import links
from configuration import config

if TYPE_CHECKING:
    import telegram


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
    "age": api.age,
    "ban": chat_management.ban,
    "botstats": dev.print_botstats,
    "brit": api.brit,
    "calc": api.calc,
    "caption": api.caption,
    "cat": api.animal,
    "catfact": api.animal,
    "covid": api.covid,
    "csgo": api.csgo,
    "fox": api.animal,
    "fw": api.audio,
    "gif": api.gif,
    "gr": api.goodreads,
    "groups": dev.groups,
    "help": help_cmd,
    "hltb": api.hltb,
    "hug": api.hug,
    "insult": api.insult,
    "jogi": api.audio,
    "joke": api.joke,
    "kick": chat_management.kick,
    "pat": api.pat,
    "pfp": api.pad_image,
    "pic": api.pic,
    "pon": api.audio,
    "search": api.search,
    "setid": api.set_steam_id,
    "shiba": api.animal,
    "spurdo": api.spurdo,
    "start": start,
    "stats": chat_management.print_stats,
    "steamstats": api.steamstats,
    "tl": api.translate,
    "tldr": api.tldr,
    "tts": api.tts,
    "ud": api.ud,
    "uwu": api.uwu,
    "wait": api.wait,
    "weather": api.weather,
    "wink": api.wink,
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
    command = command.partition('@')[0][1:]

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

    for cmd, func in commands.items():
        dispatcher.add_handler(CommandHandler(cmd, funcHandler, run_async=True))

    dispatcher.add_handler(MessageHandler(
        Filters.reply & Filters.regex(r"^s\/[\s\S]*\/[\s\S]*"),
        api.sed
    ), group=0)

    dispatcher.add_handler(MessageHandler(
        Filters.text & ~Filters.command & ~Filters.update.edited_message & ~Filters.chat_type.private,
        chat_management.increment,
    ), group=1)

    dispatcher.add_handler(MessageHandler(
        Filters.text & (Filters.entity(MessageEntity.URL) | Filters.entity(MessageEntity.TEXT_LINK)),
        links.link_handler,
    ), group=3)

    dispatcher.add_handler(CallbackQueryHandler(api.search_button))

    job_queue.run_daily(
        chat_management.clear, time=datetime.time(18, 30)
    )

    dispatcher.bot.set_my_commands([(cmd, func.__doc__) for cmd, func in commands.items()])

    updater.start_polling(drop_pending_updates=True)
    print("Started bot")
    updater.idle()


if __name__ == '__main__':
    main()
