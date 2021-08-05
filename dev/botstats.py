import sqlite3
from typing import Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    import telegram
    import telegram.ext

conn = sqlite3.connect('/db/botstats.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute(
    "CREATE TABLE IF NOT EXISTS `commands` ( "
    "`command_name` VARCHAR(255) NOT NULL UNIQUE, "
    "`command_count` INT unsigned NOT NULL DEFAULT '0', "
    "PRIMARY KEY (`command_name`))"
)


def print_botstats(update: 'telegram.Update', _context: 'telegram.ext.CallbackContext') -> None:
    """Get command usage stats"""
    if not update.message:
        return

    text: str

    # Query to get top 10 users by message count
    formula: str = "SELECT * FROM `commands` ORDER BY command_count DESC LIMIT 10"

    if update.effective_chat.type != 'private':
        cursor.execute(formula)
        rows = cursor.fetchall()
        total_commands = sum(row[1] for row in rows)
        longest: Tuple[str, int] = max(rows, key=lambda element: len(element[0]))

        if total_commands == 0:
            text = "No commands found."
        else:
            text = 'Stats for **@SuperSeriousBot**: \n'

            for command, count in rows:
                text += f"`/{command}" + (len(longest[0]) - len(command) + 1) * " " + f"- {count}`\n"

            text = text + f"\n`Total" + (len(longest[0]) - 3) * " " + f"- {total_commands}`"
    else:
        text = "This command does not work in private chats."

    update.message.reply_text(text=text)


def command_increment(command: str) -> None:
    """Increment command count"""
    formula: str = "INSERT INTO `commands` (command_name, command_count) " \
                   f"VALUES ('{command}', 1) " \
                   "ON CONFLICT(command_name) DO UPDATE SET command_count = command_count + 1"

    cursor.execute(formula)
    conn.commit()
