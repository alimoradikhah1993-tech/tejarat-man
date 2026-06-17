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

# ---------------- FLASK ----------------
app = Flask(__name__)

# ---------------- TELEGRAM ----------------
application = Application.builder().token(TOKEN).build()

# ---------------- HANDLERS ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 ربات فعال شد و متصل است")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(update.message.text)

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

# ---------------- WEB ROUTE ----------------
@app.route("/", methods=["GET"])
def home():
    return "Bot is running"

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.process_update(update)
    return "ok"

# ---------------- SAFE STARTUP (FIXED) ----------------
async def setup():
    await application.initialize()
    await application.bot.set_webhook(f"{APP_URL}/{TOKEN}")
    print("Webhook set OK")

# ---------------- RUN ----------------
if __name__ == "__main__":
    asyncio.run(setup())

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )
