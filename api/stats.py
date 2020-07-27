from time import gmtime, strftime
from pickle import load, dump
from copy import deepcopy


def load_dict():
    stats_db = open('api/stats.db', 'rb')
    try:
        stats_dict = load(stats_db)
        return stats_dict
    except EOFError:
        return {}


stats_dict = load_dict()


def clear(update):
    global stats_dict
    stats_dict = {}


def stats_check(update, context):
    global stats_dict
    # from global_stats import global_stats_dict

    msg = update.message
    chat_id = update.message.chat_id
    user_object = msg.from_user

    increment(stats_dict, chat_id, user_object)
    # increment(global_stats_dict, chat_id, user_object)

    with open('api/stats.db', 'wb') as stats_db:
        dump(stats_dict, stats_db)

    # global_stats_db = open('global_stats.db','wb')
    # dump(global_stats_dict, global_stats_db)
    # global_stats_db.close()


def increment(stats_dict, chat_id, user_object):
    if chat_id not in stats_dict.keys():
        stats_dict[chat_id] = {}
        stats_dict[chat_id]['generated'] = strftime('%d-%m-%Y', gmtime())

    if user_object not in stats_dict[chat_id]:
        stats_dict[chat_id][user_object] = 1

    else:
        stats_dict[chat_id][user_object] += 1


def stats(update, context):
    global stats_dict
    msg = update.message
    chat_id = msg.chat_id
    chat_title = msg.chat.title

    if chat_id in stats_dict.keys():
        text = f'Stats for {chat_title} \n'

        sorted_dict = deepcopy(stats_dict[chat_id])
        del sorted_dict['generated']
        sorted_dict = {k: sorted_dict[k] for k in sorted(sorted_dict, key=sorted_dict.get, reverse=True)}

        total_messages = 0
        for user in sorted_dict.keys():
            total_messages += sorted_dict[user]

        for user in list(sorted_dict.keys())[:10]:
            percentage = round((sorted_dict[user] / total_messages) * 100, 2)
            text += f'_{user.first_name} - {percentage}%_\n'

        text = text + f'\nTotal messages - {total_messages}'
        msg.reply_text(text=text)
    else:
        msg.reply_text(text='No messages here')
