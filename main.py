import os
import asyncio
import re
import pandas as pd
from datetime import datetime
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from deep_translator import GoogleTranslator
import logging

logging.basicConfig(level=logging.INFO)

# ==================== تنظیمات ====================
TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set!")

app = Flask(__name__)

# منابع گمرکات روسیه
CUSTOMS_SOURCES = {
    "websites": [
        "https://customs.gov.ru",
        "https://customs.ru",
        "https://www.rusimpex.ru",
        "https://www.russiancustoms.ru",
        "https://customs.gov.ru/statistic",
    ],
    "telegram_channels": []
}

# ==================== ابزارها ====================
async def extract_phone_email(text: str) -> tuple:
    phone_patterns = [
        r'\+7\s*\(?\d{3}\)?\s*\d{3}[\s-]?\d{2}[\s-]?\d{2}',
        r'8\s*\(?\d{3}\)?\s*\d{3}[\s-]?\d{2}[\s-]?\d{2}',
        r'\d{3}[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}',
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
    try:
        result = GoogleTranslator(source='auto', target='ru').translate(text)
        return result
    except Exception as e:
        logging.warning(f"Translation failed: {e}")
        return text

async def search_website_with_selenium(url: str, keyword: str) -> list:
    companies = []
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920x1080")
    
    try:
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(30)
        
        if "?" in url:
            search_url = f"{url}&q={keyword}"
        else:
            search_url = f"{url}/search/?q={keyword}"
        
        driver.get(search_url)
        await asyncio.sleep(5)
        
        selectors = [
            ".company-item", ".catalog-item", ".company-card", 
            ".supplier-item", ".importer-item", ".org-item",
            ".company", ".supplier", "div[class*='company']",
            "a[href*='/company/']", "a[href*='/supplier/']"
        ]
        
        for selector in selectors:
            try:
                elements = WebDriverWait(driver, 5).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                )
                if elements:
                    for elem in elements[:20]:
                        text = elem.text
                        if not text or len(text) < 5:
                            continue
                        
                        name_parts = text.split('\n')
                        name = name_parts[0].strip() if name_parts else ""
                        
                        if len(name) < 3 or len(name) > 100:
                            try:
                                title_elem = elem.find_element(By.CSS_SELECTOR, ".title, .name, h3, h4")
                                name = title_elem.text.strip()
                            except:
                                name = text[:50].strip()
                        
                        if name and len(name) > 3 and not name.startswith("http"):
                            phone, email = await extract_phone_email(text)
                            if phone and email:
                                companies.append({
                                    "name": name,
                                    "phone": phone,
                                    "email": email,
                                    "source": url
                                })
                    break
            except:
                continue
        
        driver.quit()
    except Exception as e:
        logging.error(f"Error in {url}: {e}")
    
    return companies

async def search_all_sources(keyword: str, status_message) -> list:
    all_companies = []
    russian_keyword = await translate_to_russian(keyword)
    logging.info(f"🔑 جستجو برای: {keyword} → روسی: {russian_keyword}")
    
    for site in CUSTOMS_SOURCES["websites"]:
        await status_message.edit_text(
            f"🔍 در حال جستجوی «{keyword}» ...\n"
            f"⏳ در حال بررسی: {site}\n"
            f"⏱ لطفاً منتظر بمانید..."
        )
        companies = await search_website_with_selenium(site, russian_keyword)
        all_companies.extend(companies)
        await asyncio.sleep(2)
    
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
        f"⏱ زمان تقریبی: ۱ تا ۲ دقیقه"
    )
    
    try:
        companies = await search_all_sources(keyword, msg)
        
        if not companies:
            await msg.edit_text(
                f"😕 هیچ شرکتی با شماره و ایمیل برای «{keyword}» پیدا نشد."
            )
            return
        
        df = pd.DataFrame(companies)
        safe_keyword = re.sub(r'[^\w\s]', '', keyword)
        filename = f"شرکتهای_واردکننده_{safe_keyword}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name="شرکت‌ها")
            worksheet = writer.sheets["شرکت‌ها"]
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                worksheet.column_dimensions[column_letter].width = min(max_length + 2, 50)
        
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
        await msg.edit_text(f"❌ خطا: {str(e)[:200]}")
        logging.error(f"Error in search: {e}")

# ==================== Flask Routes ====================
@app.route('/')
def home():
    return "✅ ربات جستجوی شرکت‌های واردکننده به روسیه فعال است!"

@app.route('/health')
def health():
    return "OK", 200

# ==================== اجرا ====================
if __name__ == "__main__":
    # ساخت Application
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))
    
    print("=" * 50)
    print("🤖 ربات جستجوی شرکت‌های واردکننده به روسیه")
    print("=" * 50)
    print(f"🌐 {len(CUSTOMS_SOURCES['websites'])} وب‌سایت گمرک")
    print("=" * 50)
    print("✅ ربات در حال اجراست! (بدون ترد)")
    
    # اجرای ربات در همین ترد اصلی (بدون Flask)
    application.run_polling(allowed_updates=Update.ALL_TYPES)
