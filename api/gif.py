import requests


def gif(update, context):
    """Get a random GIF from giphy"""
    params = {'api_key': ['GIPHY_API_KEY']}
    url = 'http://api.giphy.com/v1/gifs/random'

    response = requests.get(url, params=params)
    print(response.json()['data']['url'])
    update.message.reply_photo(
        photo=response.json['data']['url'],
    )
    