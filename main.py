import os
import asyncio
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN")


# ---------------- START ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 ربات فعال است\n\n"
        "دستور:\n/search product country\nمثال:\n/search milk Russia"
    )


# ---------------- STATUS ----------------
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🟢 ربات آنلاین است")


# ---------------- SIMPLE SEARCH (GOOGLE SIMULATION) ----------------
def simple_search(query: str):
    # فعلاً نسخه ساده بدون API پولی
    url = f"https://www.google.com/search?q={query}"
    return url


# ---------------- MESSAGE HANDLER ----------------
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text.startswith("/search"):
        try:
            parts = text.split(" ", 2)
            product = parts[1]
            country = parts[2]

            query = f"{product} import export companies {country}"
            result = simple_search(query)

            await update.message.reply_text(
                f"🔍 نتیجه جستجو:\n\n{result}\n\n"
                f"📦 محصول: {product}\n🌍 کشور: {country}"
            )

        except Exception as e:
            await update.message.reply_text(f"❌ خطا در دستور سرچ\n{str(e)}")

    else:
        await update.message.reply_text("⚠️ دستور ناشناخته\nاز /search استفاده کن")


# ---------------- RUN BOT ----------------
async def run():
    if not TOKEN:
        print("BOT_TOKEN missing")
        return

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(run())
