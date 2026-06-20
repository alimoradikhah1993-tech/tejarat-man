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
import json

logging.basicConfig(level=logging.INFO)

# ==================== تنظیمات ====================
TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set!")

app = Flask(__name__)

# ==================== منابع جستجوی اطلاعات تماس ====================
SEARCH_SOURCES = {
    "vk": {
        "base_url": "https://vk.com/search",
        "method": "search_companies"
    },
    "rusprofile": {
        "base_url": "https://rusprofile.ru/search",
        "method": "search_companies"
    },
    "2gis": {
        "base_url": "https://2gis.ru/search",
        "method": "search_companies"
    }
}

# ==================== تابع جستجوی اطلاعات تماس از منابع ====================

async def search_company_contacts(company_name: str) -> dict:
    """
    جستجوی اطلاعات تماس یک شرکت از منابع مختلف
    """
    contacts = {
        "name": company_name,
        "phone": None,
        "email": None,
        "source": None,
        "vk_page": None,
        "website": None
    }
    
    try:
        # 1. جستجو در Rusprofile (منبع اصلی برای شرکت‌های روسی)
        rusprofile_result = await search_rusprofile(company_name)
        if rusprofile_result:
            contacts.update(rusprofile_result)
            contacts["source"] = "Rusprofile"
            return contacts
        
        # 2. جستجو در VK
        vk_result = await search_vk(company_name)
        if vk_result:
            contacts.update(vk_result)
            contacts["source"] = "VK"
            return contacts
        
        # 3. جستجوی عمومی در گوگل (از طریق DuckDuckGo یا منبع مشابه)
        general_result = await search_general_web(company_name)
        if general_result:
            contacts.update(general_result)
            contacts["source"] = "General Web"
            return contacts
            
    except Exception as e:
        logging.error(f"Error searching for {company_name}: {e}")
    
    return contacts

# ==================== جستجو در Rusprofile ====================

async def search_rusprofile(company_name: str) -> dict:
    """
    جستجوی اطلاعات شرکت در Rusprofile
    """
    try:
        async with aiohttp.ClientSession() as session:
            # جستجوی مستقیم با نام شرکت
            search_url = f"https://rusprofile.ru/search?query={company_name}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            }
            
            async with session.get(search_url, headers=headers, timeout=15) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, "html.parser")
                    
                    # پیدا کردن اولین نتیجه
                    result_item = soup.find('div', {'class': 'company-item'})
                    if not result_item:
                        result_item = soup.find('div', {'class': 'result-item'})
                    
                    if result_item:
                        # استخراج نام شرکت
                        name_tag = result_item.find(['h3', 'h4', 'a'], {'class': 'company-name'})
                        if not name_tag:
                            name_tag = result_item.find('a')
                        name = name_tag.get_text().strip() if name_tag else company_name
                        
                        # پیدا کردن لینک صفحه شرکت
                        link = result_item.find('a')
                        if link and link.get('href'):
                            company_url = link.get('href')
                            if not company_url.startswith('http'):
                                company_url = f"https://rusprofile.ru{company_url}"
                            
                            # باز کردن صفحه شرکت برای استخراج شماره و ایمیل
                            async with session.get(company_url, headers=headers, timeout=15) as company_response:
                                if company_response.status == 200:
                                    company_html = await company_response.text()
                                    company_soup = BeautifulSoup(company_html, "html.parser")
                                    
                                    # استخراج شماره تلفن
                                    phone = None
                                    phone_patterns = [
                                        r'\+7\s*\(?\d{3}\)?\s*\d{3}[\s-]?\d{2}[\s-]?\d{2}',
                                        r'8\s*\(?\d{3}\)?\s*\d{3}[\s-]?\d{2}[\s-]?\d{2}',
                                        r'\+7\s*\d{10}',
                                    ]
                                    
                                    for pattern in phone_patterns:
                                        match = re.search(pattern, company_html)
                                        if match:
                                            phone = match.group()
                                            break
                                    
                                    # استخراج ایمیل
                                    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
                                    email_match = re.search(email_pattern, company_html)
                                    email = email_match.group() if email_match else None
                                    
                                    if phone or email:
                                        return {
                                            "name": name,
                                            "phone": phone,
                                            "email": email,
                                            "website": company_url,
                                            "vk_page": None
                                        }
    except Exception as e:
        logging.warning(f"Rusprofile error: {e}")
    
    return None

# ==================== جستجو در VK ====================

async def search_vk(company_name: str) -> dict:
    """
    جستجوی اطلاعات شرکت در VK
    """
    try:
        async with aiohttp.ClientSession() as session:
            # جستجوی گروه‌ها و صفحات شرکت در VK
            search_url = f"https://vk.com/search?c%5Bq%5D={company_name}&c%5Bsection%5D=groups"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            }
            
            async with session.get(search_url, headers=headers, timeout=15) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, "html.parser")
                    
                    # پیدا کردن اولین گروه یا صفحه
                    group_link = soup.find('a', {'class': 'group_link'})
                    if not group_link:
                        group_link = soup.find('a', href=re.compile(r'/club\d+|/public\d+'))
                    
                    if group_link and group_link.get('href'):
                        group_url = f"https://vk.com{group_link.get('href')}"
                        
                        # باز کردن صفحه گروه
                        async with session.get(group_url, headers=headers, timeout=15) as group_response:
                            if group_response.status == 200:
                                group_html = await group_response.text()
                                soup_group = BeautifulSoup(group_html, "html.parser")
                                
                                # جستجوی شماره و ایمیل در متن گروه
                                text = soup_group.get_text()
                                
                                phone = None
                                phone_patterns = [
                                    r'\+7\s*\(?\d{3}\)?\s*\d{3}[\s-]?\d{2}[\s-]?\d{2}',
                                    r'8\s*\(?\d{3}\)?\s*\d{3}[\s-]?\d{2}[\s-]?\d{2}',
                                ]
                                
                                for pattern in phone_patterns:
                                    match = re.search(pattern, text)
                                    if match:
                                        phone = match.group()
                                        break
                                
                                email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
                                email_match = re.search(email_pattern, text)
                                email = email_match.group() if email_match else None
                                
                                if phone or email:
                                    return {
                                        "name": company_name,
                                        "phone": phone,
                                        "email": email,
                                        "website": None,
                                        "vk_page": group_url
                                    }
    except Exception as e:
        logging.warning(f"VK search error: {e}")
    
    return None

# ==================== جستجوی عمومی در وب ====================

async def search_general_web(company_name: str) -> dict:
    """
    جستجوی عمومی در وب با استفاده از DuckDuckGo (رایگان و بدون محدودیت)
    """
    try:
        # استفاده از DuckDuckGo برای جستجو
        search_url = f"https://html.duckduckgo.com/html/?q={company_name.replace(' ', '+')}+%D1%82%D0%B5%D0%BB%D0%B5%D1%84%D0%BE%D0%BD+%D0%BA%D0%BE%D0%BD%D1%82%D0%B0%D0%BA%D1%82"
        
        async with aiohttp.ClientSession() as session:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            }
            
            async with session.get(search_url, headers=headers, timeout=15) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, "html.parser")
                    
                    # پیدا کردن اولین نتیجه
                    result = soup.find('a', {'class': 'result__a'})
                    if result:
                        # باز کردن صفحه وب‌سایت برای استخراج اطلاعات
                        website = result.get('href')
                        if website:
                            # بررسی اطلاعات در صفحه وب‌سایت
                            async with session.get(website, headers=headers, timeout=10) as website_response:
                                if website_response.status == 200:
                                    website_html = await website_response.text()
                                    soup_website = BeautifulSoup(website_html, "html.parser")
                                    text = soup_website.get_text()
                                    
                                    phone = None
                                    phone_patterns = [
                                        r'\+7\s*\(?\d{3}\)?\s*\d{3}[\s-]?\d{2}[\s-]?\d{2}',
                                        r'8\s*\(?\d{3}\)?\s*\d{3}[\s-]?\d{2}[\s-]?\d{2}',
                                        r'\+7\s*\d{10}',
                                    ]
                                    
                                    for pattern in phone_patterns:
                                        match = re.search(pattern, text)
                                        if match:
                                            phone = match.group()
                                            break
                                    
                                    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
                                    email_match = re.search(email_pattern, text)
                                    email = email_match.group() if email_match else None
                                    
                                    if phone or email:
                                        return {
                                            "name": company_name,
                                            "phone": phone,
                                            "email": email,
                                            "website": website,
                                            "vk_page": None
                                        }
    except Exception as e:
        logging.warning(f"General web search error: {e}")
    
    return None

# ==================== هندلر جستجوی اصلی ====================

async def search_companies(hs_code: str, company_names: list) -> list:
    """
    جستجوی اطلاعات تماس برای لیست شرکت‌ها
    """
    results = []
    total = len(company_names)
    
    for i, company_name in enumerate(company_names, 1):
        logging.info(f"🔍 جستجو برای: {company_name} ({i}/{total})")
        
        contacts = await search_company_contacts(company_name)
        
        if contacts.get("phone") or contacts.get("email"):
            results.append(contacts)
        else:
            # اگر اطلاعاتی پیدا نشد، فقط نام شرکت را ثبت کن
            results.append({
                "name": company_name,
                "phone": None,
                "email": None,
                "source": "Not Found",
                "vk_page": None,
                "website": None
            })
        
        # تاخیر برای جلوگیری از مسدود شدن
        await asyncio.sleep(2)
    
    return results

# ==================== هندلر ربات ====================

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip()
    
    if not user_input or len(user_input) < 2:
        await update.message.reply_text("❌ لطفاً کد HS را وارد کنید. مثال: 3824400000")
        return
    
    hs_code = user_input.strip()
    
    msg = await update.message.reply_text(
        f"🔍 در حال جستجوی شرکت‌های واردکننده برای کد HS: {hs_code}\n"
        f"⏳ این فرآیند ممکن است چند دقیقه طول بکشد...\n\n"
        f"📌 مرحله ۱: دریافت لیست شرکت‌ها از گمرک\n"
        f"📌 مرحله ۲: جستجوی اطلاعات تماس از منابع مختلف"
    )
    
    try:
        # ======== مرحله ۱: دریافت لیست شرکت‌ها از گمرک ========
        # اینجا شما لیست شرکت‌ها را از گمرک دریافت می‌کنید
        # فعلاً به عنوان نمونه یک لیست فرضی می‌دهیم
        
        # ⚠️ این لیست را با داده‌های واقعی گمرک جایگزین کنید
        company_names = [
            "ООО ПОЛИПЛАСТ НОВОМОСКОВСК",
            "Master Builders Solutions Azerbaijan LLC",
            "ООО ПОЛИПЛАСТУРАЛСИБ",
            "ООО ВСТЕХНОЛОГИИ",
            "ООО СУАЛПМ",
            "FARAMI GROUP LLC"
        ]
        
        await msg.edit_text(
            f"✅ مرحله ۱ کامل شد!\n"
            f"📋 تعداد شرکت‌های پیدا شده: {len(company_names)}\n\n"
            f"🔍 مرحله ۲: جستجوی اطلاعات تماس...\n"
            f"⏳ این کار ممکن است ۱-۲ دقیقه طول بکشد..."
        )
        
        # ======== مرحله ۲: جستجوی اطلاعات تماس ========
        results = await search_companies(hs_code, company_names)
        
        # ======== ایجاد فایل اکسل ========
        df = pd.DataFrame(results)
        
        # مرتب‌سازی: شرکت‌هایی که اطلاعات دارند اول بیایند
        df['has_contact'] = df['phone'].notna() | df['email'].notna()
        df = df.sort_values('has_contact', ascending=False)
        df = df.drop('has_contact', axis=1)
        
        # ستون‌های خالی را به "-" تبدیل کن
        df = df.fillna("-")
        
        filename = f"شرکتهای_واردکننده_{hs_code}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name="شرکت‌ها")
        
        # ارسال فایل به کاربر
        with open(filename, 'rb') as f:
            found_count = len([r for r in results if r.get('phone') or r.get('email')])
            
            await update.message.reply_document(
                document=f,
                filename=filename,
                caption=f"✅ <b>جستجو کامل شد!</b>\n\n"
                       f"🔑 کد HS: {hs_code}\n"
                       f"📋 کل شرکت‌ها: {len(results)}\n"
                       f"📞 دارای شماره/ایمیل: {found_count}\n"
                       f"📅 تاریخ: {datetime.now().strftime('%Y/%m/%d %H:%M')}\n\n"
                       f"💡 منابع جستجو: Rusprofile, VK, وب‌سایت‌های رسمی",
                parse_mode="HTML"
            )
        
        os.remove(filename)
        await msg.delete()
        
    except Exception as e:
        error_text = f"❌ خطا: {str(e)[:200]}"
        await msg.edit_text(error_text)
        logging.error(f"Error in search: {e}")

# ==================== بقیه کد (بدون تغییر) ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 سلام! من ربات جستجوی شرکت‌های واردکننده هستم.\n\n"
        "📌 کد HS کالای خود را وارد کنید.\n"
        "✅ مثال: 3824400000\n\n"
        "🔄 فرآیند جستجو:\n"
        "1️⃣ دریافت لیست شرکت‌ها از گمرک\n"
        "2️⃣ جستجوی اطلاعات تماس از Rusprofile، VK و وب‌سایت‌ها\n"
        "3️⃣ ارسال فایل اکسل با اطلاعات کامل"
    )

def run_flask():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def run_bot():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))
    
    print("=" * 50)
    print("🤖 ربات جستجوی شرکت‌های واردکننده (نسخه پیشرفته)")
    print("=" * 50)
    print("✅ ربات در حال اجراست!")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    run_bot()
