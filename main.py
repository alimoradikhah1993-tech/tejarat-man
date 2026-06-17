import os
import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from scraper import search_msp

# فعال کردن لاگ برای عیب‌یابی
logging.basicConfig(level=logging.INFO)

# توکن ربات را از متغیر محیطی می‌خوانیم
TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable not set!")

# دستور /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 سلام! من ربات جستجوی شرکت‌های روسی هستم.\n"
        "نام کالا را به فارسی یا انگلیسی بفرستید تا شرکت‌های مرتبط را پیدا کنم.\n"
        "مثال: یخچال  یا  Refrigerator"
    )

# پردازش پیام‌های معمولی (جستجو)
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyword = update.message.text.strip()
    if not keyword:
        await update.message.reply_text("❌ لطفاً یک کلمه برای جستجو وارد کنید.")
        return
    
    await update.message.reply_text(f"🔍 در حال جستجوی شرکت‌های مرتبط با «{keyword}» ...")
    
    try:
        # اجرای اسکرپر
        companies = await search_msp(keyword)
        
        if not companies:
            await update.message.reply_text("😕 نتیجه‌ای پیدا نشد. لطفاً کلمه دیگری试试 کنید.")
        else:
            # لیست شرکت‌ها را به صورت شماره‌دار نمایش می‌دهیم
            result = "📋 شرکت‌های پیدا شده:\n\n" + "\n".join([f"{i+1}. {c}" for i, c in enumerate(companies[:20])])
            if len(companies) > 20:
                result += f"\n\n... و {len(companies)-20} شرکت دیگر"
            await update.message.reply_text(result)
            
    except Exception as e:
        await update.message.reply_text(f"❌ خطا در جستجو: {str(e)}")

# تابع اصلی
def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))
    
    print("🤖 ربات روشن شد...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
