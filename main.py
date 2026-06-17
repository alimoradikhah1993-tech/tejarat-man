import os
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# ---------------- ENV ----------------
TOKEN = os.getenv("BOT_TOKEN")
APP_URL = os.getenv("APP_URL")  # https://your-app.onrender.com

# ---------------- FLASK ----------------
app = Flask(__name__)

# ---------------- BOT ----------------
application = Application.builder().token(TOKEN).build()


# ---------------- HANDLERS ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 ربات فعال است (Webhook Mode)")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🟢 آنلاین هستم")


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    await update.message.reply_text(f"📩 دریافت شد: {text}")


application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("status", status))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))


# ---------------- ROUTES ----------------
@app.route("/", methods=["GET"])
def home():
    return "Bot is running"


@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json(force=True)

    update = Update.de_json(data, application.bot)

    # اجرای async در Flask
    asyncio.run(application.process_update(update))

    return "ok"


# ---------------- WEBHOOK SET ----------------
def set_webhook():
    url = f"{APP_URL}/{TOKEN}"
    asyncio.run(application.bot.set_webhook(url=url))
    print("✅ Webhook set:", url)


# ---------------- RUN ----------------
def run():
    if not TOKEN or not APP_URL:
        print("❌ BOT_TOKEN یا APP_URL تنظیم نشده")
        return

    set_webhook()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))


if __name__ == "__main__":
    run()
