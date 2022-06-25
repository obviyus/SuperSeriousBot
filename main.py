import os

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from config.logger import logger
from config.options import config


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Start command handler.
    """
    await update.message.reply_text(f"👋 @{update.effective_user.username}")
    logger.info(f"/start command received from @{update.effective_user.username}")


if __name__ == "__main__":
    application = ApplicationBuilder().token(config["TELEGRAM"]["TOKEN"]).build()

    start_handler = CommandHandler("start", start)
    application.add_handler(start_handler)

    if config["TELEGRAM"]["UPDATER"] == "webhook":
        application.run_webhook(
            listen="0.0.0.0",
            port=int(os.environ.get("PORT", "8443")),
            url_path=config["TELEGRAM"]["TOKEN"],
            webhook_url=config["TELEGRAM"]["WEBHOOK_URL"],
        )
    else:
        application.run_polling()
