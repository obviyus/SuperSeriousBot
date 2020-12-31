from telegram import InlineKeyboardMarkup, InlineKeyboardButton
import qbittorrentapi
import time


qbt_client = qbittorrentapi.Client()  # uses env vars
qbt_client.search.update_plugins()

items_per_page = 3
cols_per_page = 2
total_items = 24


def construct_message(magnet_list, desc_list, min_offset):
    max_offset = min(min_offset + items_per_page, len(magnet_list))
    kb_menu = [
        InlineKeyboardButton(text=f'Torrent {i+1}', callback_data=f'{i}')
        for i in range(min_offset, max_offset)
    ]

    kb_menu = [kb_menu[i:i + cols_per_page] for i in range(0, min(items_per_page, len(kb_menu)), cols_per_page)]

    if len(kb_menu[-1]) % 2 == 1:
        kb_menu[-1].insert(0, InlineKeyboardButton(text='<', callback_data='-2'))
        kb_menu[-1].append(InlineKeyboardButton(text='>', callback_data='-1'))
    else:
        kb_menu.append([
            InlineKeyboardButton(text='<', callback_data='-2'),
            InlineKeyboardButton(text='>', callback_data='-1')
        ])

    text = '\n\n'.join(desc_list[min_offset:max_offset])

    return text, InlineKeyboardMarkup(kb_menu)


def search(update, context):
    """Search torrents from multiple aggregators"""
    message = update.message
    query = ' '.join(context.args)
    if not query:
        message.reply_text(
            "*Usage:* `/search {QUERY}`\n"
            "*Example:* `/convert mr brightside` \n\n"
            "Shows 24 results max"
        )
        return

    context.chat_data.clear()
    sent_message = message.reply_text(text="Fetching results...", quote=True, parse_mode='HTML')
    context.chat_data['search_msg_id'] = sent_message.message_id

    search_job = qbt_client.search_start(pattern=query, category='all', plugins='all')
    while search_job.status()[0].total <= total_items and search_job.status()[0].status != 'Stopped':
        time.sleep(.1)
    search_job.stop()
    # first result is jackett error, disabling or uninstalling doesn't work
    search_results = list(search_job.results(limit=total_items, offset=1).results)
    search_job.delete()

    context.chat_data['desc_list'] = []
    context.chat_data['offset'] = 0
    for result in search_results[:]:
        # TPB returns a placeholder result if nothing is found
        if result.fileName == "No results returned" and result.nbSeeders == 0 and result.nbLeechers == 0 and result.fileSize == 0:
            search_results.remove(result)
        else:
            # markdown doesn't work
            context.chat_data['desc_list'].append(
                f"<b>Name:</b> <i>{result.fileName}</i>\n"
                f"<b>Seeders:</b> <i>{result.nbSeeders}</i>\n"
                f"<b>Size:</b> <i>{round(result.fileSize/(1024**3),2)} GB</i>"
            )

    context.chat_data['magnet_list'] = [
        f'{result.fileName}:\n\n{result.fileUrl}'
        for result in search_results
    ]

    if not context.chat_data['desc_list']:
        sent_message.edit_text(text="No results found")
    else:
        text, kb_menu = construct_message(
            context.chat_data['magnet_list'],
            context.chat_data['desc_list'],
            context.chat_data['offset']
        )
        sent_message.edit_text(
            text=f'Page 1:\n\n{text}',
            reply_markup=kb_menu,
            parse_mode='HTML'
        )


def search_button(update, context):

    query = update.callback_query
    index = int(query.data)

    if query.from_user != query.message.reply_to_message.from_user:
        query.answer('You are not the search invoker')
        return

    if 'search_msg_id' not in context.chat_data or query.message.message_id != context.chat_data['search_msg_id']:
        query.answer('Search expired')
        query.edit_message_text(text='Search expired')
        return

    magnet_list = context.chat_data['magnet_list']
    desc_list = context.chat_data['desc_list']
    offset = context.chat_data['offset']

    if index == -1:  # next page
        if offset + items_per_page >= len(magnet_list):
            query.answer('Last page, cant go further')
            return
        else:
            text, kb = construct_message(
                magnet_list,
                desc_list,
                offset + items_per_page
            )
            context.chat_data['offset'] += items_per_page
            text = f'Page {int(offset / items_per_page + 2)}:\n\n{text}'
    elif index == -2:  # previous page
        if offset == 0:
            query.answer('First page, cant go back')
            return
        else:
            text, kb = construct_message(
                magnet_list,
                desc_list,
                offset - items_per_page
            )
            context.chat_data['offset'] -= items_per_page
            text = f'Page {int(offset / items_per_page)}:\n\n{text}'
    else:
        query.answer('Sending magnet...')

        magnet = magnet_list[index]
        if not magnet_list[index].startswith('https'):
            magnet = magnet.replace('\n\n', '\n\n<code>') + '</code>'

        query.message.reply_to_message.reply_text(magnet, quote=True, parse_mode='HTML')
        return

    query.edit_message_text(text=text, reply_markup=kb, parse_mode='HTML')
    query.answer()
