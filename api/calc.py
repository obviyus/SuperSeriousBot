import wolframalpha
from configuration import config
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import telegram


def calc(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Calculate anything using wolframalpha"""
    if update.message:
        message: 'telegram.Message' = update.message
    else:
        return
    query: str = ' '.join(context.args) if context.args else ''

    text: str
    if not query:
        text = "*Usage:* `/calc {QUERY}`\n"\
               "*Example:* `/calc 1 cherry to grams`"
    else:
        client: wolframalpha.Client = wolframalpha.Client(config["WOLFRAM_APP_ID"])
        result: wolframalpha.Result = client.query(query)

        if result.success == 'true':
            text = next(result.results).text
        else:
            text = "Invalid query"

    message.reply_text(text=text)
