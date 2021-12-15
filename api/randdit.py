from typing import TYPE_CHECKING
from time import sleep
import requests

import logging

if TYPE_CHECKING:
    import telegram
    import telegram.ext

headers = {
    "User-Agent": "@SuperSeriousBot (by /u/obviyus)",
}


def get_post(url: str) -> str:
    url = requests.get(url, headers=headers)
    logging.info(url.url)

    sleep_time = 2
    for _ in range(0, 5):
        try:
            result = requests.get(url.url).json()[0]["data"]["children"][0]["data"][
                "url"
            ]
            return result
        except KeyError:
            if "search.json" in url.url:
                return "Subreddit does not exist."
            sleep(sleep_time)
            sleep_time *= 2

    return "Too many requests. Try again in a while."


def randdit(update: "telegram.Update", context: "telegram.ext.CallbackContext") -> None:
    """Get a random post from a subreddit"""
    if not update.message:
        return

    subreddit: str = context.args[0] if context.args else ""

    if not subreddit:
        update.message.reply_text(text=get_post("https://www.reddit.com/random.json"))
    else:
        update.message.reply_text(
            text=get_post(f"https://www.reddit.com/r/{subreddit}/random.json")
        )
