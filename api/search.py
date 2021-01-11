from telegram import InlineKeyboardMarkup, InlineKeyboardButton
import qbittorrentapi
import time
from typing import TYPE_CHECKING, Optional, Tuple, List

if TYPE_CHECKING:
    import telegram


qbt_client: qbittorrentapi.Client = qbittorrentapi.Client()  # uses env vars
qbt_client.search.install_plugin(sources=[
    "https://raw.githubusercontent.com/libellula/qbt-plugins/c81ccd168f3d8e4e8d8492bcef19e1740cc18aa7/nyaapantsu.py"  # Nyaa.net
])
qbt_client.search.update_plugins()

items_per_page: int = 3
cols_per_page: int = 2
total_items: int = 24


def construct_message(
    magnet_list: List[str],
    desc_list: List[str],
    min_offset: int
) -> Tuple[str, InlineKeyboardMarkup]:

    max_offset: int = min(
        min_offset + items_per_page,
        len(magnet_list)
    )

    kb: list = [
        InlineKeyboardButton(text=f'Torrent {i+1}', callback_data=f'{i}')
        for i in range(min_offset, max_offset)
    ]

    kb_menu: list = [
        kb[i:i + cols_per_page]
        for i in range(0, min(items_per_page, len(kb)), cols_per_page)
    ]

    if len(kb_menu[-1]) % 2 == 1:
        kb_menu[-1].insert(0, InlineKeyboardButton(text='<', callback_data='-2'))
        kb_menu[-1].append(InlineKeyboardButton(text='>', callback_data='-1'))
    else:
        kb_menu.append([
            InlineKeyboardButton(text='<', callback_data='-2'),
            InlineKeyboardButton(text='>', callback_data='-1')
        ])

    text: str = '\n\n'.join(desc_list[min_offset:max_offset])

    return text, InlineKeyboardMarkup(kb_menu)


def search(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Search torrents from multiple aggregators"""

    message: Optional['telegram.Message'] = update.message
    query: str = ' '.join(context.args) if context.args else ''

    if not message:
        return

    if not query:
        message.reply_text(
            "*Usage:* `/search {QUERY}`\n"
            "*Example:* `/search mr brightside` \n\n"
            "Shows 24 results max"
        )
        return

    if context.chat_data is not None:
        context.chat_data.clear()
        sent_message: 'telegram.Message' = message.reply_text(
            text="Fetching results...",
            quote=True,
            parse_mode='HTML'
        )
        context.chat_data['search_msg_id'] = sent_message.message_id

        search_job: qbittorrentapi.search = qbt_client.search_start(
            pattern=query,
            category='all',
            plugins='all'
        )

        while search_job.status()[0].total <= total_items and search_job.status()[0].status != 'Stopped':
            time.sleep(.1)

        search_job.stop()
        # first result is jackett error, disabling or uninstalling doesn't work
        search_results: list = list(search_job.results(limit=total_items, offset=1).results)
        search_job.delete()

        context.chat_data['desc_list'] = []
        context.chat_data['offset'] = 0
        for result in search_results[:]:
            if (
                # TPB returns a placeholder result if nothing is found
                (
                    result.fileName == "No results returned"
                    and result.nbSeeders == 0
                    and result.nbLeechers == 0
                    and result.fileSize == 0
                )
                # Jackett error still shows up sometimes
                or result.fileName.startswith("Jackett: api key error!")
            ):
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
            text: str
            kb_menu: InlineKeyboardMarkup
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


def search_button(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:

    query: Optional['telegram.CallbackQuery'] = update.callback_query
    if not query or not query.message or not query.message.reply_to_message:
        return
    index: int = int(query.data) if query.data else 0

    if query.from_user != query.message.reply_to_message.from_user:
        query.answer('You are not the search invoker')
        return

    if (
        not context.chat_data
        or 'search_msg_id' not in context.chat_data
        or query.message.message_id != context.chat_data['search_msg_id']
    ):
        query.answer('Search expired')
        query.edit_message_text(text='Search expired')
        return

    magnet_list: List[str] = context.chat_data['magnet_list']
    desc_list: List[str] = context.chat_data['desc_list']
    offset: int = context.chat_data['offset']

    text: str
    kb_menu: InlineKeyboardMarkup

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

        magnet: str = magnet_list[index]
        if not magnet_list[index].startswith('https'):
            magnet = magnet.replace('\n\n', '\n\n<code>') + '</code>'

        query.message.reply_to_message.reply_text(
            magnet,
            quote=True,
            parse_mode='HTML'
        )
        return

    query.edit_message_text(text=text, reply_markup=kb, parse_mode='HTML')
    query.answer()
