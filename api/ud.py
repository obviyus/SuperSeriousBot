import emoji
from requests import get


def ud(update, context):
    """Command to query UD for word definition."""
    message = update.message
    word = ' '.join(context.args)

    if not word:
        text = "*Usage:* `/ud {QUERY}`\n"\
               "*Example:* `/ud boomer`\n"
    else:
        result = get(f"http://api.urbandictionary.com/v0/define?term={word}")
        result = result.json()

        if result['list']:
            # Sort to get result with most thumbs up
            max_thumbs, idx = 0, 0
            for index, value in enumerate(result['list']):
                if max_thumbs < value["thumbs_up"]:
                    idx = index
                    max_thumbs = value["thumbs_up"]

            result = result['list'][idx]

            heading = result["word"]
            definition = result["definition"]
            example = result["example"]
            thumbs = emoji.emojize(f":thumbs_up: × {max_thumbs}")

            text = f"*{heading}*\n\n{definition}\n\n_{example}_\n\n`{thumbs}`"
        else:
            text = "No entry found.",

    context.bot.send_message(
        chat_id=message.chat_id,
        text=text,
    )
