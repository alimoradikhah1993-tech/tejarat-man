import os
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN")
APP_URL = os.getenv("APP_URL")

if not TOKEN or not APP_URL:
    raise ValueError("BOT_TOKEN or APP_URL is not set")

app = Flask(__name__)

application = Application.builder().token(TOKEN).build()

# ---------------- HANDLERS ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 ربات وصل شد و فعاله")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(update.message.text)

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

# ---------------- WEBHOOK ----------------
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.process_update(update)
    return "ok"

@app.route("/", methods=["GET"])
def home():
    return "Bot is running"

# ---------------- SET WEBHOOK ----------------
def set_webhook():
    url = f"{APP_URL}/{TOKEN}"
    application.bot.set_webhook(url=url)
    print("Webhook set:", url)

# ---------------- START ----------------
if __name__ == "__main__":
    set_webhook()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
