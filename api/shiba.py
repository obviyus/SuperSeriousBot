from requests import get


def shiba(update, context):
    """ Command to return a random Shiba Inu image"""

    response = get('http://shibe.online/api/shibes?count=1&urls=true&httpsUrls=false')
    response = response.json()

    context.bot.send_photo(
        photo=response[0],
        chat_id=update.message.chat_id
    )
