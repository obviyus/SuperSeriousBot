import logging

from telegram.ext import (Updater, CommandHandler)

from api.translate import translate
from api.ud import ud
from api.currency import currency
from chat_management.kick import kick


def start(bot, update):
    bot.send_message(chat_id=update.message.chat_id, text="Hi.")


def main():
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    updater = Updater(token="743193671:AAEBo4aW2VnLcQDIjIuIN3rxRiq4lA_HDPE")

    dispatcher = updater.dispatcher

    # Handlers
    start_handler = CommandHandler('start', start)
    kick_handler = CommandHandler('kick', kick)
    ud_handler = CommandHandler('ud', ud)
    translate_handler = CommandHandler('tl', translate)
    currency_handler = CommandHandler('convert', currency)

    dispatcher.add_handler(start_handler)
    dispatcher.add_handler(kick_handler)
    dispatcher.add_handler(ud_handler)
    dispatcher.add_handler(translate_handler)
    dispatcher.add_handler(currency_handler)

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
