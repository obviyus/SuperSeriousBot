import logging

from telegram.ext import (Updater, CommandHandler)

from api.translate import translate
from api.ud import ud
from api.currency import currency
from api.calc import calc
from api.tts import tts
from api.hltb import hltb
from api.countdown import countdown
from api.time import time
from api.countdown import countdown

from chat_management.kick import kick

from configuration import config


def start(bot, update):
    bot.send_message(
        chat_id=update.message.chat_id,
        text="Hi."
    )


def main():
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    updater = Updater(token=config["TELEGRAM_BOT_TOKEN"])

    dispatcher = updater.dispatcher

    # Handlers
    start_handler = CommandHandler('start', start)
    kick_handler = CommandHandler('kick', kick)
    ud_handler = CommandHandler('ud', ud)
    translate_handler = CommandHandler('tl', translate)
    currency_handler = CommandHandler('convert', currency)
    hltb_handler = CommandHandler('hltb', hltb)
    countdown_handler = CommandHandler('countdown', countdown)
    calc_hanlder = CommandHandler('calc', calc)
    tts_handler = CommandHandler('tts', tts)
    time_handler = CommandHandler('time', time)
    countdown_handler = CommandHandler('countdown', countdown)
    calc_hanlder = CommandHandler('calc', calc)
    tts_handler = CommandHandler('tts', tts)
    
    dispatcher.add_handler(start_handler)
    dispatcher.add_handler(kick_handler)
    dispatcher.add_handler(ud_handler)
    dispatcher.add_handler(translate_handler)
    dispatcher.add_handler(currency_handler)
    dispatcher.add_handler(hltb_handler)
    dispatcher.add_handler(countdown_handler)
    dispatcher.add_handler(calc_hanlder)
    dispatcher.add_handler(tts_handler)
    dispatcher.add_handler(time_handler)
    dispatcher.add_handler(countdown_handler)
    dispatcher.add_handler(calc_hanlder)
    dispatcher.add_handler(tts_handler)

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
