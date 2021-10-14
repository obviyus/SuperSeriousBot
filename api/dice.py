import re, random

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import telegram
    import telegram.ext


def dice(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Roll a XdY + Z dice"""
    if update.message:
        message: 'telegram.Message' = update.message
    else:
        return
    
    result: str
    rollList = []
    roll: str = ' '.join(context.args)
    die = re.compile('([1-9]\d*)?d([1-9]\d*)([\+\-][1-9]\d*)?').match(roll)

    if not die:
        result = "*Usage:* `/dice XdY +/- Z`\n" \
                      "Rolls a die of Y sides X times, gets the sum and adds or subtracts a modifier Z \n" \
                      "*Example:* `/dice 2d20+4`\n"
    else:
        for i in range(1 if not die.group(1) else int(die.group(1))):
            rollList.append(random.randint(1,int(die.group(2))))
        result = f"Roll: [{rollList}]\nResult = {sum(rollList) if not die.group(3) else sum(rollList) + int(die.group(3))}"
        
    message.reply_text(text=result)       
