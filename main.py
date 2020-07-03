from telegram.ext import (Updater, MessageHandler, Filters, CommandHandler,
                          ConversationHandler, CallbackQueryHandler, RegexHandler)
import logging

logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

updater = Updater(token="743193671:AAEBo4aW2VnLcQDIjIuIN3rxRiq4lA_HDPE")

dispatcher = updater.dispatcher

def start(bot, update):
	bot.send_message(chat_id = update.message.chat_id, text = "Hi.")

start_handler = CommandHandler('start', start)

dispatcher.add_handler(start_handler)

updater.start_polling()
updater.idle()