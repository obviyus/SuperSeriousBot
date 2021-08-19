from typing import Tuple, TYPE_CHECKING

import redis

if TYPE_CHECKING:
    import telegram
    import telegram.ext

r = redis.StrictRedis(host='redis', port='6379', db=0, charset="utf-8", decode_responses=True)


def print_botstats(update: 'telegram.Update', _context: 'telegram.ext.CallbackContext') -> None:
    """Get command usage stats"""
    if not update.message:
        return

    text: str
    rows = []
    for key in r.scan_iter("*"):
        if key.startswith("seen:"):
            continue
        rows.append((key, int(r.get(key))))
    rows = sorted(rows, key=lambda x: x[1], reverse=True)[:10]

    if len(rows) == 0:
        text = "No commands found."
    else:
        total_commands = sum(row[1] for row in rows)
        longest: Tuple[str, int] = max(rows, key=lambda x: len(x[0]))

        text = 'Stats for **@SuperSeriousBot**: \n'
        for command, count in rows:
            text += f"`/{command}" + (len(longest[0]) - len(command) + 1) * " " + f"- {count}`\n"
        text = text + f"\n`Total" + (len(longest[0]) - 3) * " " + f"- {total_commands}`"

    update.message.reply_text(text=text)


def command_increment(command: str) -> None:
    """Increment command count"""
    if command != "botstats":
        r.incr(command, 1)
