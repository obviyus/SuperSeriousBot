from requests import get


def wink(update, context):
    """Reply with a wink GIF"""
    response(update.message, 'wink')


def pat(update, context):
    """Reply with a pat GIF"""
    response(update.message, 'pat')


def hug(update, context):
    """Reply with a hug GIF"""
    response(update.message, 'hug')


def response(message, action):
    """Query API for appropriate action"""
    response = get(f'https://some-random-api.ml/animu/{action}').json()

    try:
        message.reply_to_message.reply_animation(animation=response['link'])
    except AttributeError:
        message.reply_animation(animation=response['link'])
