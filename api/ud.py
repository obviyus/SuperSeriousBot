from typing import TYPE_CHECKING, Dict

import emoji
from requests import get

if TYPE_CHECKING:
    import telegram
    import telegram.ext


def ud(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Query Urban Dictionary for word definition"""
    if update.message:
        message: 'telegram.Message' = update.message
    else:
        return

    word: str = ' '.join(context.args)

    text: str
    if not word:
        text = "*Usage:* `/ud {QUERY}`\n" \
               "*Example:* `/ud boomer`\n"
    else:
        result: Dict = get(f"http://api.urbandictionary.com/v0/define?term={word}").json()

        if result['list']:
            # Sort to get result with most thumbs up
            result: Dict = max(result, key=lambda x: x['thumbs_up'])

            text = f"""*{result["word"]}*\n\n{result["definition"]}\n\n_{result["example"]}_\n\n`""" \
                   f"""{emoji.emojize(f":thumbs_up: × {result['thumbs_up']}")}`"""
        else:
            text = "No entry found."

    message.reply_text(text=text)
