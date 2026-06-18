import os
import asyncio
import re
import pandas as pd
from datetime import datetime
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import logging
import threading
import aiohttp
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)

# ==================== تنظیمات ====================
TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set!")

app = Flask(__name__)

# ==================== منابع ====================
CUSTOMS_SOURCES = {
    "websites": [
        "https://customs.gov.ru",
        "https://customs.ru",
        "https://www.rusimpex.ru",
        "https://www.russiancustoms.ru",
    ]
}

# ==================== ابزارها ====================
async def extract_phone_email(text: str) -> tuple:
    phone_patterns = [
        r'\+7\s*\(?\d{3}\)?\s*\d{3}[\s-]?\d{2}[\s-]?\d{2}',
        r'8\s*\(?\d{3}\)?\s*\d{3}[\s-]?\d{2}[\s-]?\d{2}',
        r'\+7\s*\d{10}',
        r'8\s*\d{10}',
    ]
    
    phone = None
    for pattern in phone_patterns:
        match = re.search(pattern, text)
        if match:
            phone = match.group()
            break
    
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    email_match = re.search(email_pattern, text)
    email = email_match.group() if email_match else None
    
    return phone, email

async def translate_to_russian(text: str) -> str:
    translation_dict = {
        "سیمان": "цемент",
        "بتن": "бетон",
        "ماهی": "рыба",
        "غذایی": "продукты",
        "شیمیایی": "химия",
        "ساختمان": "строительство",
        "مواد": "материалы",
        "پلاستیک": "пластик",
        "فولاد": "сталь",
        "آهن": "железо",
        "cement": "цемент",
        "concrete": "бетон",
        "fish": "рыба",
        "steel": "сталь",
        "plastic": "пластик",
    }
    
    text_lower = text.lower().strip()
    if text_lower in translation_dict:
        return translation_dict[text_lower]
    
    words = text_lower.split()
    translated_words = []
    for word in words:
        if word in translation_dict:
            translated_words.append(translation_dict[word])
        else:
            translated_words.append(word)
    
    return " ".join(translated_words)

async def search_website_simple(url: str, keyword: str) -> list:
    companies = []
    try:
        async with aiohttp.ClientSession() as session:
            search_url = f"{url}/search/?q={keyword}"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            
            async with session.get(search_url, headers=headers, timeout=10) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, "html.parser")
                    
                    for text in soup.stripped_strings:
                        if len(text) > 10:
                            phone, email = await extract_phone_email(text)
                            if phone and email:
                                name = text[:50].strip()
                                if len(name) > 3:
                                    companies.append({
                                        "name": name,
                                        "phone": phone,
                                        "email": email,
                                        "source": url
                                    })
                                    if len(companies) >= 5:
                                        break
    except Exception as e:
        logging.warning(f"Error in {url}: {e}")
    
    return companies

async def search_all_sources(keyword: str, status_message) -> list:
    all_companies = []
    russian_keyword = await translate_to_russian(keyword)
    logging.info(f"🔑 جستجو برای: {keyword} → روسی: {russian_keyword}")
    
    for site in CUSTOMS_SOURCES["websites"]:
        try:
            await status_message.edit_text(
                f"🔍 در حال جستجوی «{keyword}» ...\n"
                f"⏳ در حال بررسی: {site}\n"
                f"⏱ لطفاً منتظر بمانید..."
            )
            companies = await search_website_simple(site, russian_keyword)
            all_companies.extend(companies)
            await asyncio.sleep(1)
        except Exception as e:
            logging.error(f"Error searching {site}: {e}")
    
    seen = set()
    unique_companies = []
    for company in all_companies:
        key = f"{company['name']}_{company['phone']}"
        if key not in seen:
            seen.add(key)
            unique_companies.append(company)
    
    return unique_companies

# ==================== هندلرهای ربات ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 سلام! من ربات جستجوی شرکت‌های واردکننده به روسیه هستم.\n\n"
        "📌 هر کلمه (فارسی یا انگلیسی) بفرستید تا جستجو کنم.\n"
        "✅ نتیجه شامل شرکت‌های دارای شماره و ایمیل می‌شود.\n"
        "📊 خروجی به صورت فایل اکسل ارسال می‌شود.\n\n"
        "🔍 مثال: 'سیمان' یا 'cement' یا 'fish'"
    )

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyword = update.message.text.strip()
    
    if not keyword or len(keyword) < 2:
        await update.message.reply_text("❌ حداقل ۲ کاراکتر وارد کنید.")
        return
    
    msg = await update.message.reply_text(
        f"🔍 در حال جستجوی شرکت‌های واردکننده «{keyword}» ...\n"
        f"⏳ صادرکننده گرامی، لطفاً منتظر بمانید...\n\n"
        f"⏱ زمان تقریبی: ۳۰ ثانیه تا ۱ دقیقه"
    )
    
    try:
        companies = await search_all_sources(keyword, msg)
        
        if not companies:
            await msg.edit_text(
                f"😕 هیچ شرکتی با شماره و ایمیل برای «{keyword}» پیدا نشد.\n\n"
                f"💡 نکات:\n"
                f"• از کلمات عمومی‌تر استفاده کنید\n"
                f"• کلمه را به انگلیسی وارد کنید"
            )
            return
        
        df = pd.DataFrame(companies)
        safe_keyword = re.sub(r'[^\w\s]', '', keyword)
        filename = f"شرکتهای_واردکننده_{safe_keyword}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name="شرکت‌ها")
        
        with open(filename, 'rb') as f:
            await update.message.reply_document(
                document=f,
                filename=filename,
                caption=f"✅ <b>{len(companies)} شرکت</b> پیدا شد.\n"
                       f"🔑 کلمه جستجو: {keyword}\n"
                       f"📅 تاریخ: {datetime.now().strftime('%Y/%m/%d %H:%M')}",
                parse_mode="HTML"
            )
        
        os.remove(filename)
        await msg.delete()
        
    except Exception as e:
        error_text = f"❌ خطا: {str(e)[:150]}"
        await msg.edit_text(error_text)
        logging.error(f"Error in search: {e}")

# ==================== Flask Routes ====================
@app.route('/')
def home():
    return "✅ ربات جستجوی شرکت‌های واردکننده به روسیه فعال است!"

@app.route('/health')
def health():
    return "OK", 200

# ==================== اجرا ====================
def run_flask():
    """اجرای Flask در یک ترد جداگانه"""
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def run_bot():
    """راه‌اندازی ربات"""
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))
    
    print("=" * 50)
    print("🤖 ربات جستجوی شرکت‌های واردکننده به روسیه")
    print("=" * 50)
    print(f"🌐 {len(CUSTOMS_SOURCES['websites'])} وب‌سایت")
    print("=" * 50)
    print("✅ ربات در حال اجراست!")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    # اجرای Flask در ترد جداگانه (برای باز کردن پورت)
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # اجرای ربات در ترد اصلی
    run_bot()
