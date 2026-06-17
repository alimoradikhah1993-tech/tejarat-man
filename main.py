import os
import asyncio
import threading
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from scraper import search_msp

app = Flask(__name__)

@app.route('/')
def home():
    return "ربات تلگرام فعال است!"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))

TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable not set!")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 سلام! من ربات جستجوی شرکت‌های روسی هستم.\n"
        "نام کالا را به فارسی یا انگلیسی بفرستید تا شرکت‌های مرتبط را پیدا کنم."
    )

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyword = update.message.text.strip()
    if not keyword:
        await update.message.reply_text("❌ لطفاً یک کلمه برای جستجو وارد کنید.")
        return
    
    await update.message.reply_text(f"🔍 در حال جستجوی شرکت‌های مرتبط با «{keyword}» ...")
    
    try:
        companies = await search_msp(keyword)
        if not companies:
            await update.message.reply_text("😕 نتیجه‌ای پیدا نشد.")
        else:
            result = "📋 شرکت‌های پیدا شده:\n\n" + "\n".join([f"{i+1}. {c}" for i, c in enumerate(companies[:20])])
            if len(companies) > 20:
                result += f"\n\n... و {len(companies)-20} شرکت دیگر"
            await update.message.reply_text(result)
    except Exception as e:
        await update.message.reply_text(f"❌ خطا: {str(e)}")

def run_telegram():
    telegram_app = Application.builder().token(TOKEN).build()
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))
    print("🤖 ربات روشن شد...")
    telegram_app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    # اجرای همزمان فلاسک و ربات تلگرام
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    run_telegram()
