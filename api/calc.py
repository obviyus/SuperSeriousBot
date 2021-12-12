from typing import TYPE_CHECKING

import wolframalpha

from configuration import config

if TYPE_CHECKING:
    import telegram
    import telegram.ext

client: wolframalpha.Client = wolframalpha.Client(config["WOLFRAM_APP_ID"])


def calc(update: "telegram.Update", context: "telegram.ext.CallbackContext") -> None:
    """Calculate anything using wolframalpha"""
    if update.message:
        message: "telegram.Message" = update.message
    else:
        return
    query: str = " ".join(context.args) if context.args else ""

    text: str
    if not query:
        text = "*Usage:* `/calc {QUERY}`\n*Example:* `/calc 1 cherry to grams`"
    else:
        result: wolframalpha.Result = client.query(query)

        try:
            text = next(result.results).text
        except StopIteration:
            text = "Invalid query."

    message.reply_text(text=text)
