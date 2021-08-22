import sqlite3
import datetime
from typing import TYPE_CHECKING, Tuple

import redis

if TYPE_CHECKING:
    import telegram
    import telegram.ext

conn = sqlite3.connect('/db/stats.db', check_same_thread=False)
r = redis.StrictRedis(host='redis', port='6379', db=0, charset="utf-8", decode_responses=True)


def check_table_exists(table_name: str) -> bool:
    cursor = conn.cursor()

    cursor.execute(f"""SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'""")
    return len(cursor.fetchall()) == 1


def print_stats(update: 'telegram.Update', _context: 'telegram.ext.CallbackContext') -> None:
    """Get daily chat stats starting 0:00 IST"""
    if not update.message:
        return

    chat_id: int = update.message.chat_id
    chat_title: str = update.message.chat.title
    text: str

    if check_table_exists(table_name=str(chat_id)) and update.effective_chat.type != 'private':
        cursor = conn.cursor()

        # Query to get top 10 users by message count
        formula: str = f"SELECT * FROM `{chat_id}` ORDER BY message_count DESC LIMIT 10"
        cursor.execute(formula)
        rows = cursor.fetchall()
        total_messages = sum(row[1] for row in rows)

        if total_messages == 0:
            text = "No messages found."
        else:
            text = f'**Stats for {chat_title}** \n'
            user_object = update.message.from_user
            longest: Tuple[str, int] = max(rows, key=lambda x: len(x[0]))

            # Ignore special case for user
            if user_object.id == 1060827049:
                text += f'`{user_object.first_name}' + (
                        len(longest[0]) - len(user_object.first_name) + 1
                ) * ' ' + '- 100% degen`\n'

            for user, count in rows:
                percentage = round((count / total_messages) * 100, 2)
                text += f"`{user}" + (len(longest[0]) - len(user) + 1) * " " + f"- {percentage}%`\n"
            text = text + f"\n`Total" + (len(longest[0]) - 4) * " " + f"- {total_messages}`"
    else:
        text = "No messages found."

    update.message.reply_text(text=text)


def print_gstats(update: 'telegram.Update', _context: 'telegram.ext.CallbackContext') -> None:
    """Get total chat stats"""
    if not update.message:
        return

    chat_id: int = update.message.chat_id
    chat_title: str = update.message.chat.title
    text: str

    if check_table_exists(table_name=str(chat_id) + "_total") and update.effective_chat.type != 'private':
        cursor = conn.cursor()

        # Query to get top 10 users by message count
        formula: str = f"SELECT * FROM `{chat_id}_total` ORDER BY message_count DESC LIMIT 10"
        cursor.execute(formula)
        rows = cursor.fetchall()

        total_messages = sum(row[1] for row in rows)

        if total_messages == 0:
            text = "No messages found."
        else:
            text = f'**Total Stats for {chat_title}**\n'
            user_object = update.message.from_user
            longest: Tuple[str, int] = max(rows, key=lambda x: len(x[0]))

            # Ignore special case for user
            if user_object.id == 1060827049:
                text += f'`{user_object.first_name}' + (
                        len(longest[0]) - len(user_object.first_name) + 1
                ) * ' ' + '- 100% degen`\n'

            for user, count in rows:
                text += f"`{user}" + (len(longest[0]) - len(user) + 1) * " " + f"- {count}`\n"
            text = text + f"\n`Total" + (len(longest[0]) - 4) * " " + f"- {total_messages}`"
    else:
        text = "No messages found."

    update.message.reply_text(text=text)


def increment_total(chat_id: str) -> None:
    if check_table_exists(table_name=chat_id):
        cursor = conn.cursor()

        if not check_table_exists(table_name=chat_id + "_total"):
            formula: str = f"CREATE TABLE IF NOT EXISTS `{chat_id}_total` ( " \
                           "`user_name` VARCHAR(255) NOT NULL UNIQUE, " \
                           "`message_count` INT unsigned NOT NULL DEFAULT '0', " \
                           "PRIMARY KEY (`user_name`))"

            cursor.execute(formula)

        cursor.execute(f"SELECT * FROM `{chat_id}`")
        for user, count in cursor.fetchall():
            increment_formula = f"INSERT INTO `{chat_id}_total` (user_name, message_count) " \
                                f"VALUES ('{user}', {count}) " \
                                f"ON CONFLICT(user_name) DO UPDATE SET message_count = message_count + {count}"
            cursor.execute(increment_formula)
            conn.commit()


def clear(_context: 'telegram.ext.CallbackContext') -> None:
    """Clear all stat tables"""
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE '%_total'")
    for (table_name,) in cursor.fetchall():
        increment_total(table_name)
        formula = f"DELETE FROM `{table_name}`"
        cursor.execute(formula)

    conn.commit()


def increment(update: 'telegram.Update', _context: 'telegram.ext.CallbackContext') -> None:
    """Increment message count for a user"""
    if not update.message:
        return

    chat_id: int = update.message.chat_id
    user_object = update.message.from_user

    # Set last seen in Redis
    r.set(f'seen:{user_object.username}', datetime.datetime.now().isoformat())

    cursor = conn.cursor()
    if not check_table_exists(table_name=str(chat_id)):
        formula: str = f"CREATE TABLE IF NOT EXISTS `{chat_id}` ( " \
                       "`user_name` VARCHAR(255) NOT NULL UNIQUE, " \
                       "`message_count` INT unsigned NOT NULL DEFAULT '0', " \
                       "PRIMARY KEY (`user_name`))"
        cursor.execute(formula)

    increment_formula = f"INSERT INTO `{chat_id}` (user_name, message_count) " \
                        f"VALUES ('{user_object.first_name}', 1) " \
                        "ON CONFLICT(user_name) DO UPDATE SET message_count = message_count + 1"
    cursor.execute(increment_formula)
    conn.commit()
