import re
import random

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import telegram
    import telegram.ext


def dice(update: "telegram.Update", context: "telegram.ext.CallbackContext") -> None:
    """Roll a XdY + Z dice"""
    if update.message:
        message: "telegram.Message" = update.message
    else:
        return

    result: str
    roll_list = []
    roll: str = " ".join(context.args)
    die = re.compile(r"([1-9]\d*)?[d|D]([1-9]\d*)([\+\-][1-9]\d*)?").match(roll)

    if not die:
        result = (
            "*Usage:* `/dice XdY +/- Z`\n"
            "Rolls a die of Y sides X (default is 1) times, gets the sum and "
            "adds or subtracts a modifier Z (optional)\n"
            "*Example:* `/dice 2d20+4`\n"
        )
    else:
        for i in range(int(die.group(1) or 1)):
            roll_list.append(random.randint(1, int(die.group(2))))
        result = (
            f"Roll: [{roll_list}]\nResult = {sum(roll_list) + int(die.group(3) or 0)}"
        )

    message.reply_text(text=result)
