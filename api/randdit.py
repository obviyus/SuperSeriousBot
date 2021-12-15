from typing import TYPE_CHECKING

import requests

from configuration import config

if TYPE_CHECKING:
    import telegram
    import telegram.ext

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
}


def get_post(url: str) -> str:
    url = requests.get(url, headers=headers).json()[0]["data"]["children"][0]["data"][
        "url"
    ]
    return url


def randdit(update: "telegram.Update", context: "telegram.ext.CallbackContext") -> None:
    """Get a random post from a subreddit"""
    if not update.message:
        return

    subreddit: str = context.args[0] if context.args else ""

    if not subreddit:
        update.message.reply_text(text=get_post("https://www.reddit.com/random.json"))
    else:
        search_url = f"https://www.reddit.com/subreddits/search.json?q={subreddit}"
        if len(requests.get(search_url, headers=headers).json()["data"]["children"]):
            update.message.reply_text(
                text=get_post(f"https://www.reddit.com/r/{subreddit}/random.json")
            )
        else:
            update.message.reply_text(
                text=get_post("https://www.reddit.com/random.json")
            )
