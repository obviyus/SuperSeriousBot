from random import choices

import requests
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config import logger

images = set()


async def get_image():
    """
    Get a random image from Imgur.
    """
    url = ""

    while not url:
        chars: str = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghiklmnopqrstuvwxyz"
        address: str = "https://i.imgur.com/" + "".join(choices(chars, k=5)) + ".jpg"
        r = requests.get(address)

        # Ignore any images < 1000B
        if r.url == address and int(r.headers["content-length"]) > 1000:
            url = address

    logger.info("Seeding image: %s", url)
    images.add(url)


async def worker_image_seeder(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Worker that seeds images from Imgur.
    """
    logger.info("Pre-seeding 10 random Imgur images...")
    limit = 10

    # Run the worker in a loop asynchronously
    for _ in range(limit):
        await context.application.create_task(get_image())


async def pic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get random images from imgur"""
    await update.message.reply_photo(
        photo=images.pop(),
        parse_mode=ParseMode.HTML,
    )

    if len(images) < 5:
        context.job_queue.run_once(worker_image_seeder, 0)
