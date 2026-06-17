import os
import logging
from flask import Flask
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# --------------------
# Logging
# --------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

# --------------------
# Flask for Render
# --------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

# --------------------
# Telegram Handlers
# --------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 ربات جستجوی بازار روسیه و آذربایجان\n\n"
        "نام کالا را ارسال کنید.\n\n"
        "مثال:\n"
        "ماهی منجمد\n"
        "PET Flakes\n"
        "الیاف پلی استر"
    )

    await update.message.reply_text(text)

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🟢 ربات فعال است\n"
        "🟢 اتصال تلگرام برقرار است\n"
        "🟢 سرور آماده است"
    )

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    product = update.message.text

    await update.message.reply_text(
        f"🔍 درخواست دریافت شد:\n\n"
        f"{product}\n\n"
        f"⏳ در حال جستجو...\n"
        f"لطفاً منتظر بمانید."
    )

# --------------------
# Main
# --------------------
def run_bot():
    token = os.getenv("BOT_TOKEN")

    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, search)
    )

    application.run_polling()

if __name__ == "__main__":
    run_bot()
