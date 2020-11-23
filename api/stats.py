import mysql.connector
from mysql.connector import errorcode

from configuration import config

try:
    conn = mysql.connector.connect(
        host="127.0.0.1",
        user=config["MYSQL_USERNAME"],
        passwd=config["MYSQL_PW"],
        database="chat_stats"
    )
    cursor = conn.cursor()
except mysql.connector.Error as err:
    if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
        raise errorcode.ER_ACCESS_DENIED_ERROR("Something is wrong with your user name or password")
    elif err.errno == errorcode.ER_BAD_DB_ERROR:
        raise errorcode.ER_BAD_DB_ERROR("Database does not exist")
    else:
        raise RuntimeError(err)


def check_table_exists(table_name):
    cursor.execute(f"""
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_name = {table_name}
        """)
    return cursor.fetchone()[0] == 1


def print_stats(update, context):
    """Get daily chat stats starting 0:00 IST"""
    chat_id = update.message.chat_id
    chat_title = update.message.chat.title

    # Query to get top 10 users by message count
    formula = f"SELECT * FROM `{chat_id}` ORDER BY message_count DESC LIMIT 10"

    if check_table_exists(table_name=chat_id):
        cursor.execute(formula)
        rows = cursor.fetchall()
        total_messages = sum(row[1] for row in rows)

        if total_messages == 0:
            text = "No messages found."
        else:
            text = f'Stats for **{chat_title}** \n'
            user_object = update.message.from_user

            # Ignore
            if user_object.id == 1060827049:
                text += f'_{user_object.first_name} - 100% degen_\n'

            for user, count in rows:
                percentage = round((count / total_messages) * 100, 2)
                text += f'_{user} - {percentage}%_\n'

            text = text + f'\nTotal messages - {total_messages}'
    else:
        text = "No messages found."

    update.message.reply_text(text=text)


def clear(context):
    """"Reset message count to 0 for a chat"""
    for (table_name,) in cursor.execute("SHOW TABLES"):
        cursor.execute(f"TRUNCATE TABLE `{table_name}`")
    conn.commit()


def increment(update, context):
    """Increment message count for a user"""
    chat_id = update.message.chat_id
    user_object = update.message.from_user

    if not check_table_exists(table_name=chat_id):
        formula = f"CREATE TABLE `{chat_id}` ( " \
                  "`user_name` VARCHAR(255) NOT NULL UNIQUE, " \
                  "`message_count` INT unsigned NOT NULL DEFAULT '0', " \
                  "PRIMARY KEY (`user_name`))"

        cursor.execute(formula)

    increment_formula = f"INSERT INTO `{chat_id}` (user_name, message_count) " \
                        f"VALUES ('{user_object.first_name}', 1) " \
                        "ON DUPLICATE KEY UPDATE message_count = message_count + 1"
    cursor.execute(increment_formula)
    conn.commit()
