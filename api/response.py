from requests import get


def wink(update, context):
    response(update.message, 'wink')


def pat(update, context):
    response(update.message, 'pat')


def hug(update, context):
    response(update.message, 'hug')


def response(message, action):
    response = get(f'https://some-random-api.ml/animu/{action}').json()

    try:
        message.reply_to_message.reply_animation(animation=response['link'])
    except AttributeError:
        message.reply_animation(animation=response['link'])
