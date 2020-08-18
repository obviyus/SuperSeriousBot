from requests import get


def insult(update, context):
    """Get a random insult"""

    response = get('https://evilinsult.com/generate_insult.php?lang=en&type=json')
    response = response.json()

    try:
        update.message.reply_to_message.reply_text(text=response['insult'])
    except AttributeError:
        update.message.reply_text(text=response['insult'])
