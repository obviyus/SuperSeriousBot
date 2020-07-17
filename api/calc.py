import wolframalpha
from configuration import config


def calc(update, context):
    """Command to calculate anything using wolframalpha."""
    message = update.message
    query = ' '.join(context.args)

    if not query:
        text = "*Usage:* `/calc {QUERY}`\n"\
               "*Example:* `/calc 1 cherry to grams`"
    else:
        client = wolframalpha.Client(config["WOLFRAM_APP_ID"])
        result = client.query(query)

        if result.success:
            text = next(result.results).text
        else:
            text = f"Invalid query\n{result.tips['tip']['@text']}"

    context.bot.send_message(chat_id=message.chat_id, text=text)
