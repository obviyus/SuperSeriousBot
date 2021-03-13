import sqlite3
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import telegram
    import telegram.ext

conn = sqlite3.connect('/db/stats.db', check_same_thread=False)
cursor = conn.cursor()


def check_table_exists(table_name: int) -> bool:
    cursor.execute(f"""SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'""")
    return len(cursor.fetchall()) == 1


def print_stats(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Get daily chat stats starting 0:00 IST"""
    if not update.message:
        return

    chat_id: int = update.message.chat_id
    chat_title: str = update.message.chat.title
    text: str

    # Query to get top 10 users by message count
    formula: str = f"SELECT * FROM `{chat_id}` ORDER BY message_count DESC LIMIT 10"

    if check_table_exists(table_name=chat_id) and update.effective_chat.type != 'private':
        cursor.execute(formula)
        rows = cursor.fetchall()
        total_messages = sum(row[1] for row in rows)

        if total_messages == 0:
            text = "No messages found."
        else:
            text = f'Stats for **{chat_title}** \n'
            user_object = update.message.from_user

            # Ignore special case for user
            if user_object.id == 1060827049:
                text += f'_{user_object.first_name} - 100% degen_\n'

            for user, count in rows:
                percentage = round((count / total_messages) * 100, 2)
                text += f'_{user} - {percentage}%_\n'

            text = text + f'\nTotal messages - {total_messages}'
    else:
        text = "No messages found."

    update.message.reply_text(text=text)


def clear(context: 'telegram.ext.CallbackContext') -> None:
    """"Reset message count to 0 for a chat"""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")

    for (table_name,) in cursor.fetchall():
        formula = f"DROP TABLE IF EXISTS `{table_name}`"
        cursor.execute(formula)

    conn.commit()


def increment(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Increment message count for a user"""
    if not update.message:
        return

    chat_id: int = update.message.chat_id
    user_object = update.message.from_user

    if not check_table_exists(table_name=chat_id):
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
