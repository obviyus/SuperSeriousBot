from typing import Tuple, TYPE_CHECKING
from .botstats import r

if TYPE_CHECKING:
    import telegram
    import telegram.ext


def print_reddit_stats(
    update: "telegram.Update", context: "telegram.ext.CallbackContext"
) -> None:
    """Get subreddit search stats"""
    if not update.message:
        return

    text: str
    rows = []
    for key in r.scan_iter("r:*"):
        rows.append((key, int(r.get(key))))
    rows = sorted(rows, key=lambda x: x[1], reverse=True)[:10]

    if len(rows) == 0:
        text = "No subreddits found."
    else:
        total_commands = sum(row[1] for row in rows)
        longest: Tuple[str, int] = max(rows, key=lambda x: len(x[0]))

        text = f"Reddit stats for **@{context.bot.username}**: \n"
        for command, count in rows:
            command = command[2:]
            text += (
                f"`/r/{command}"
                + (len(longest[0]) - len(command) + 1) * " "
                + f"- {count}`\n"
            )
        text = text + f"\n`Total" + f" - {total_commands}`"

    update.message.reply_text(text=text)


def reddit_increment(subreddit: str) -> None:
    """Increment subreddit search count"""
    if subreddit != "botstats":
        r.incr(f"r:{subreddit}", 1)
