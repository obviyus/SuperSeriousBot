import requests
from configuration import config


def gif(update, context):
    """Get a random GIF from giphy"""
    params = {'api_key': config['GIPHY_API_KEY']}
    url = 'http://api.giphy.com/v1/gifs/random'

    response = requests.get(url, params=params)
    url = response.json()['data']['images']['original']['url']

    update.message.reply_animation(
        animation=url,
    )
    