from googletrans import Translator
from telegram import Update, Bot

def translate(bot: Bot, update: Update):
    if update.effective_message.reply_to_message:
        message = update.effective_message.reply_to_message

    translator = Translator()
