from requests import get


def shiba(update, context):
    """ Command to return a random Shiba Inu image"""

    response = get('http://shibe.online/api/shibes?count=1&urls=true&httpsUrls=false')
    response = response.json()

    context.bot.send_photo(
        photo=response[0],
        chat_id=update.message.chat_id
    )


def fox(update, context):
    """ Command to return a random Fox image"""

    response = get('https://randomfox.ca/floof/')
    response = response.json()

    context.bot.send_photo(
        photo=response['image'],
        chat_id=update.message.chat_id
    )


def cat(update, context):
    """ Command to return a random Cat image"""

    response = get('https://api.thecatapi.com/v1/images/search')
    response = response.json()

    context.bot.send_photo(
        photo=response[0]['url'],
        chat_id=update.message.chat_id
    )


def catfact(update, context):
    """ Command to return a random Cat Fact"""

    response = get('https://cat-fact.herokuapp.com/facts/random')
    response = response.json()

    update.message.reply_text(
        text=response["text"]
    )
