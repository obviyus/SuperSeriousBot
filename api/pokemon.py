from requests import get


def pokemon(update, context):
    """Command to query UD for word definition."""
    message = update.message
    query = ' '.join(context.args)
    parse_mode = 'Markdown'

    if not query:
        text = "*Usage:* `/pokemon {QUERY}`\n"\
               "*Example:* `/pokemon Charmander`\n"
    else:
        games, abilities, types = [], [], []
        response = get(f'https://pokeapi.co/api/v2/pokemon/{query}')
        response = response.json()

        for game_index in response['game_indices']:
            games.append(game_index['version']['name'].title())
        for ability in response['abilities']:
            abilities.append(ability['ability']['name'].title())
        for each_type in response['types']:
            types.append(each_type['type']['name'].title())

        name = response['name'].title()
        species = response['species']['name'].title()
        height = response['height']
        weight = response['weight']
        sprite = response['sprites']['front_default']

        text = f"<b>{name}</b>\n\n"\
               f"<b>Species</b>: {species}\n<b>Height</b>: {height/10} m\n<b>Weight</b>: {weight/10} kg\n\n"\
               f"<b>Types</b>: {', '.join(types)}\n<b>Abilities</b>: {', '.join(abilities)}\n\n<b>Games</b>: {', '.join(games)}\n"\
               f"<a href='{sprite}'>&#8205;</a>"
        parse_mode = 'HTML'

    message.reply_text(
        text=text,
        parse_mode=parse_mode,
        disable_web_page_preview=False,
    )
