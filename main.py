from telegram.ext import (Updater, MessageHandler, Filters, CommandHandler,
                          ConversationHandler, CallbackQueryHandler, RegexHandler)
import logging

from chat_management.kick import kick

def start(bot, update):
	bot.send_message(chat_id = update.message.chat_id, text = "Hi.")

def main():
	logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

	updater = Updater(token="743193671:AAEBo4aW2VnLcQDIjIuIN3rxRiq4lA_HDPE")

	dispatcher = updater.dispatcher

	#Handlers
	start_handler = CommandHandler('start', start)
	kick_handler = CommandHandler('kick', kick)

	dispatcher.add_handler(start_handler)
	dispatcher.add_handler(kick_handler)

	updater.start_polling()
	updater.idle()


if __name__ == '__main__':
    main()
