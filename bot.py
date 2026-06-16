import asyncio
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = "YOUR_BOT_TOKEN"
CHAT_ID = "YOUR_CHAT_ID"

bot = Bot(token=TOKEN)


# -----------------------------
# ارسال پیام معمولی
# -----------------------------
async def _send(text):
    async with Bot(token=TOKEN) as bot:
        await bot.send_message(chat_id=CHAT_ID, text=text)


def send_report(text):
    try:
        asyncio.run(_send(text))
    except Exception as e:
        print("BOT ERROR:", e)


# -----------------------------
# /start command
# -----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Bot is active!\n\n"
        "📊 AI Trade system started\n"
        "⏳ Every 15 minutes analysis runs"
    )


# -----------------------------
# error handler (خیلی مهم)
# -----------------------------
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    err = str(context.error)

    print("❌ TELEGRAM ERROR:", err)

    try:
        await bot.send_message(
            chat_id=CHAT_ID,
            text=f"🚨 Bot Error:\n{err}"
        )
    except:
        pass


# -----------------------------
# start bot polling (برای /start)
# -----------------------------
def run_bot():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_error_handler(error_handler)

    print("🤖 Bot polling started...")
    app.run_polling()
