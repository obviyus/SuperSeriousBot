"""Commands for general use."""

from importlib import import_module

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from commands.runtime import (
    command_wrapper,
    disabled,
    is_command_enabled,
    validate_command_meta,
)
from commands.runtime import (
    every_message_action as every_message_action,
)
from commands.runtime import (
    usage_string as usage_string,
)
from utils.decorators import get_command_meta, get_registered_commands
from utils.messages import get_message

COMMAND_MODULE_NAMES = (
    "animals", "ask", "book", "calc", "cron", "define", "dl", "gif", "graph",
    "habit", "highlight", "hltb", "insult", "joke", "meme", "model", "ping",
    "quote", "remind", "search", "spurdo", "store", "summon", "tldr",
    "transcribe", "translate", "ud", "uwu", "weather", "whitelist",
)
MANAGEMENT_MODULE_NAMES = ("blocks", "botstats", "stats")

for module_name in COMMAND_MODULE_NAMES:
    import_module(f"{__name__}.{module_name}")
for module_name in MANAGEMENT_MODULE_NAMES:
    import_module(f"management.{module_name}")

habit = import_module(f"{__name__}.habit")
cron_module = import_module(f"{__name__}.cron")
summon = import_module(f"{__name__}.summon")
highlight_button_handler = import_module(
    f"{__name__}.highlight"
).highlight_button_handler

# Import side effects above register decorated commands.
list_of_commands = get_registered_commands()

command_handler_list = []
command_triggers: set[str] = set()


for command in list_of_commands:
    meta = get_command_meta(command)
    if not meta:
        continue

    validate_command_meta(command, meta)
    assert meta.triggers is not None
    assert meta.description is not None
    assert meta.usage is not None
    assert meta.example is not None

    handler = command if is_command_enabled(command) else disabled
    handler = command_wrapper(handler, command_triggers)

    command_handler_list.append(CommandHandler(meta.triggers, handler))

    command_triggers.update(meta.triggers)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)

    if not message:
        return
    query = update.callback_query
    if not query or not query.data:
        return

    handler = {
        "cr": cron_module.cron_button_handler,
        "hb": habit.habit_button_handler,
        "hl": highlight_button_handler,
        "sg": summon.summon_keyboard_button,
    }.get(query.data.split(":", 1)[0])
    if handler:
        await handler(update, context)
        return

    await query.answer("No function found for this button.")
