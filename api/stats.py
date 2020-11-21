import mysql.connector

mydb = mysql.connector.connect(
    host="127.0.0.1",
    user="root",
    passwd="password",
    database="chat_stats"
)
cursor = mydb.cursor()


def check_table_exists(dbcon, tablename):
    dbcur = dbcon.cursor()
    dbcur.execute(f"""
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_name = {tablename}
        """)
    if dbcur.fetchone()[0] == 1:
        dbcur.close()
        return True

    dbcur.close()
    return False


def print_stats(update, context):
    """Get daily chat stats"""
    chat_id = update.message.chat_id
    chat_title = update.message.chat.title

    formula = f"SELECT * FROM `{chat_id}` ORDER BY message_count DESC LIMIT 10"
    print(formula)

    if check_table_exists(mydb, chat_id):
        cursor.execute(formula)
        rows = cursor.fetchall()
        total_messages = sum(row[1] for row in rows)

        if total_messages == 0:
            text = "No messages here."
        else:
            text = f'Stats for {chat_title} \n'
            for user, count in rows:
                percentage = round((count / total_messages) * 100, 2)
                text += f'_{user} - {percentage}%_\n'

            text = text + f'\nTotal messages - {total_messages}'
    else:
        text = "No messages found."

    update.message.reply_text(text=text)


def clear(update):
    formula = f'UPDATE `{update.message.chat_id}` SET message_count = 0'
    cursor.execute(formula)


def increment(update, context):
    chat_id = update.message.chat_id
    user_object = update.message.from_user

    if not check_table_exists(mydb, chat_id):
        formula = f"CREATE TABLE `{chat_id}` ( " \
                  "`user_name` VARCHAR(255) NOT NULL UNIQUE, " \
                  "`message_count` INT unsigned NOT NULL DEFAULT '0', " \
                  "PRIMARY KEY (`user_name`))"
        cursor.execute(formula)

    increment_formula = f"INSERT INTO `{chat_id}` (user_name, message_count) " \
                        f"VALUES ('{user_object.first_name}', 1) " \
                        "ON DUPLICATE KEY UPDATE message_count = message_count + 1"
    cursor.execute(increment_formula)

