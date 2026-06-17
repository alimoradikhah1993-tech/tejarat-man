import os
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN")
APP_URL = os.getenv("APP_URL")  # مثلا https://your-app.onrender.com

app = Flask(__name__)

# ---------------- BOT ----------------
application = Application.builder().token(TOKEN).build()


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


# ---------------- WEBHOOK ROUTE ----------------
@app.route("/", methods=["GET"])
def home():
    return "Bot is running"


@app.route(f"/{TOKEN}", methods=["POST"])
async def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    await application.process_update(update)
    return "ok"


# ---------------- START WEBHOOK ----------------
def set_webhook():
    url = f"{APP_URL}/{TOKEN}"
    application.bot.set_webhook(url=url)
    print("Webhook set:", url)


def run():
    application.initialize()
    set_webhook()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))


if __name__ == "__main__":
    run()
