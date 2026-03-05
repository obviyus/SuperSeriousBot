from time import perf_counter

from telegram import Update
from telegram.ext import ContextTypes

from utils.decorators import command
from utils.messages import get_message


@command(
    triggers=["ping"],
    usage="/ping",
    example="/ping",
    description="Pong.",
)
async def ping(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return
    start_time = perf_counter()
    probe_message = await message.reply_text(text="⏳ Measuring...")
    latency_ms = max((perf_counter() - start_time) * 1000, 0)
    await probe_message.edit_text(text=f"pong ({latency_ms:.2f}ms)")
