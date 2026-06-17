import os
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise ValueError("BOT_TOKEN is not set")

# ---------------- BOT INSTANCE (ONLY ONE) ----------------
bot = Bot(token=TOKEN)

# ---------------- SIMPLE SEND (FIXED - NO asyncio.run) ----------------
async def send_report(text, chat_id):
    await bot.send_message(chat_id=chat_id, text=text)

# ---------------- HANDLERS ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Bot is active!\n"
        "📊 System running"
    )

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(update.message.text)

# ---------------- ERROR HANDLER ----------------
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    try:
        await bot.send_message(
            chat_id=update.effective_chat.id if update and hasattr(update, "effective_chat") else "YOUR_CHAT_ID",
            text=f"🚨 Error: {context.error}"
        )
    except:
        pass

# ---------------- MAIN ----------------
def run_bot():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    app.add_error_handler(error_handler)

    print("Bot started...")
    app.run_polling()

if __name__ == "__main__":
    run_bot()
