import os
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# ---------------- ENV ----------------
TOKEN = os.getenv("BOT_TOKEN")
APP_URL = os.getenv("APP_URL")

if not TOKEN:
    raise ValueError("BOT_TOKEN is not set")
if not APP_URL:
    raise ValueError("APP_URL is not set")

# ---------------- FLASK APP ----------------
app = Flask(__name__)

# ---------------- TELEGRAM BOT ----------------
application = Application.builder().token(TOKEN).build()


# ---------------- HANDLERS ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 ربات فعال است (Webhook Mode)")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🟢 ربات آنلاین است")


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"📩 پیام شما: {update.message.text}")


application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("status", status))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))


# ---------------- WEB ROUTES ----------------
@app.route("/", methods=["GET"])
def home():
    return "Bot is running"
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json(force=True)

    update = Update.de_json(data, application.bot)

    application.process_update(update)

    return "ok"

# ---------------- SET WEBHOOK ----------------
def set_webhook():
    url = f"{APP_URL}/{TOKEN}"
    application.bot.set_webhook(url=url)
    print("Webhook set:", url)

# ---------------- RUN SERVER ----------------
def run():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    loop.run_until_complete(application.initialize())

    set_webhook()

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
