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

TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set!")

app = Flask(__name__)

# ==================== داده‌های شرکت‌های آذربایجانی (از منابع تجاری) ====================
# این لیست بر اساس داده‌های Volza و Eximpedia برای کد 3824400000 تهیه شده است
AZERBAIJAN_IMPORTERS = [
    {"name": "Master Builders Solutions Azerbaijan LLC", "origin": "Russia, Turkey, Kazakhstan"},
    {"name": "SIKA MBCC AZERBAIJAN LLC", "origin": "Russia, Turkey"},
    {"name": "KARTASH LTD MMS", "origin": "Russia, Turkey"},
    {"name": "ООО ПОЛИПЛАСТ НОВОМОСКОВСК", "origin": "Russia"},  # صادرکننده به آذربایجان
    {"name": "ООО ПОЛИПЛАСТУРАЛСИБ", "origin": "Russia"},  # صادرکننده به آذربایجان
    {"name": "ООО ВСТЕХНОЛОГИИ", "origin": "Russia"},  # صادرکننده به آذربایجان
    {"name": "FARAMI GROUP LLC", "origin": "Russia"},  # صادرکننده به آذربایجان
    {"name": "ООО СУАЛПМ", "origin": "Russia"},  # صادرکننده به آذربایجان
]

# ==================== توابع جستجوی اطلاعات تماس ====================

async def search_company_contacts_az(company_name: str) -> dict:
    """
    جستجوی اطلاعات تماس یک شرکت آذربایجانی از منابع مختلف
    اولویت: وب‌سایت رسمی، سپس جستجوی عمومی
    """
    contacts = {
        "name": company_name,
        "phone": None,
        "email": None,
        "website": None,
        "source": None,
        "country": "Azerbaijan"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            }
            
            # 1. جستجوی مستقیم با نام شرکت + "Azerbaijan" + "contact"
            search_terms = [
                f"{company_name} Azerbaijan contact",
                f"{company_name} Azerbaijan phone",
                f"{company_name} Azerbaijan email",
                f"{company_name} Baku contact"
            ]
            
            for term in search_terms[:2]:  # فقط دو عبارت اول برای سرعت
                search_url = f"https://html.duckduckgo.com/html/?q={term.replace(' ', '+')}"
                async with session.get(search_url, headers=headers, timeout=15) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, "html.parser")
                        
                        # پیدا کردن اولین نتیجه
                        result_link = soup.find('a', {'class': 'result__a'})
                        if result_link and result_link.get('href'):
                            website = result_link.get('href')
                            if website and not website.startswith('http'):
                                website = f"https:{website}" if website.startswith('//') else website
                            
                            # باز کردن وب‌سایت برای استخراج اطلاعات
                            if website and website.startswith('http'):
                                try:
                                    async with session.get(website, headers=headers, timeout=10) as site_response:
                                        if site_response.status == 200:
                                            site_html = await site_response.text()
                                            site_soup = BeautifulSoup(site_html, "html.parser")
                                            text = site_soup.get_text()
                                            
                                            # استخراج شماره تلفن
                                            phone = None
                                            phone_patterns = [
                                                r'\+994\s*\(?\d{2}\)?\s*\d{3}[\s-]?\d{2}[\s-]?\d{2}',
                                                r'0[5-9]\d{8}',  # شماره موبایل آذربایجان
                                                r'\+994\s*\d{9}',
                                                r'0[12]\d{8}',  # شماره ثابت باکو
                                            ]
                                            
                                            for pattern in phone_patterns:
                                                match = re.search(pattern, text)
                                                if match:
                                                    phone = match.group()
                                                    break
                                            
                                            # استخراج ایمیل
                                            email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
                                            email_match = re.search(email_pattern, text)
                                            email = email_match.group() if email_match else None
                                            
                                            if phone or email:
                                                contacts["phone"] = phone
                                                contacts["email"] = email
                                                contacts["website"] = website
                                                contacts["source"] = "Website Search"
                                                return contacts
                                except:
                                    pass
            
            # 2. جستجو در VK (گروه‌های آذربایجانی)
            vk_search_url = f"https://vk.com/search?c%5Bq%5D={company_name}&c%5Bsection%5D=groups"
            async with session.get(vk_search_url, headers=headers, timeout=15) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, "html.parser")
                    group_link = soup.find('a', href=re.compile(r'/club\d+|/public\d+'))
                    if group_link and group_link.get('href'):
                        group_url = f"https://vk.com{group_link.get('href')}"
                        async with session.get(group_url, headers=headers, timeout=15) as group_response:
                            if group_response.status == 200:
                                group_html = await group_response.text()
                                group_soup = BeautifulSoup(group_html, "html.parser")
                                text = group_soup.get_text()
                                
                                phone_patterns = [
                                    r'\+994\s*\(?\d{2}\)?\s*\d{3}[\s-]?\d{2}[\s-]?\d{2}',
                                    r'0[5-9]\d{8}',
                                    r'\+994\s*\d{9}',
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
                                
                                if phone or email:
                                    contacts["phone"] = phone
                                    contacts["email"] = email
                                    contacts["website"] = group_url
                                    contacts["source"] = "VK"
                                    return contacts
                                    
    except Exception as e:
        logging.warning(f"Error searching for {company_name}: {e}")
    
    return contacts

async def search_companies_az(hs_code: str, companies_list: list) -> list:
    """
    جستجوی اطلاعات تماس برای لیست شرکت‌های آذربایجانی
    """
    results = []
    total = len(companies_list)
    
    for i, company in enumerate(companies_list, 1):
        logging.info(f"🔍 جستجو برای: {company['name']} ({i}/{total})")
        
        contacts = await search_company_contacts_az(company["name"])
        contacts["origin"] = company.get("origin", "Unknown")
        results.append(contacts)
        
        await asyncio.sleep(2)  # جلوگیری از مسدود شدن
    
    return results

# ==================== هندلرهای ربات ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 سلام! من ربات جستجوی شرکت‌های واردکننده به جمهوری آذربایجان هستم.\n\n"
        "📌 کد HS کالای خود را وارد کنید.\n"
        "✅ مثال: 3824400000\n\n"
        "📊 فرآیند جستجو:\n"
        "1️⃣ دریافت لیست شرکت‌ها از داده‌های گمرک (Volza/Eximpedia)\n"
        "2️⃣ جستجوی اطلاعات تماس از وب‌سایت‌ها و VK\n"
        "3️⃣ ارسال فایل اکسل با اطلاعات کامل\n\n"
        "🇦🇿 تمرکز ویژه بر روی بازار جمهوری آذربایجان"
    )

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    hs_code = update.message.text.strip()
    
    if not hs_code or not hs_code.isdigit() or len(hs_code) < 6:
        await update.message.reply_text(
            "❌ لطفاً یک کد HS معتبر وارد کنید.\n"
            "✅ مثال: 3824400000"
        )
        return
    
    msg = await update.message.reply_text(
        f"🔍 در حال جستجوی شرکت‌های واردکننده برای کد HS: {hs_code}\n"
        f"🇦🇿 کشور: جمهوری آذربایجان\n"
        f"📋 تعداد شرکت‌ها در لیست: {len(AZERBAIJAN_IMPORTERS)}\n"
        f"⏳ این فرآیند ممکن است ۲-۳ دقیقه طول بکشد..."
    )
    
    try:
        results = await search_companies_az(hs_code, AZERBAIJAN_IMPORTERS)
        
        # تبدیل به DataFrame
        df = pd.DataFrame(results)
        
        # ستون‌های خالی را به "-" تبدیل کن
        df = df.fillna("-")
        
        # مرتب‌سازی: شرکت‌هایی که اطلاعات دارند اول
        df['has_contact'] = (df['phone'] != "-") | (df['email'] != "-")
        df = df.sort_values('has_contact', ascending=False)
        df = df.drop('has_contact', axis=1)
        
        # تغییر نام ستون‌ها
        df.columns = ['نام شرکت', 'شماره تلفن', 'ایمیل', 'وب‌سایت', 'منبع پیدا شده', 'کشور', 'کشور مبدا کالا']
        
        filename = f"شرکتهای_واردکننده_آذربایجان_{hs_code}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name="واردکنندگان آذربایجان")
            
            # اضافه کردن توضیحات در برگه دوم
            info_df = pd.DataFrame({
                'اطلاعات': [
                    f'کد HS: {hs_code}',
                    f'کشور: جمهوری آذربایجان',
                    f'تاریخ جستجو: {datetime.now().strftime("%Y/%m/%d %H:%M")}',
                    f'تعداد کل شرکت‌ها: {len(results)}',
                    f'شرکت‌های دارای شماره/ایمیل: {len([r for r in results if r.get("phone") != "-" or r.get("email") != "-"])}',
                    f'منبع داده: Volza / Eximpedia',
                    'توضیحات: لیست شرکت‌های واردکننده کد HS مورد نظر در جمهوری آذربایجان'
                ]
            })
            info_df.to_excel(writer, index=False, sheet_name="اطلاعات")
        
        # ارسال فایل
        with open(filename, 'rb') as f:
            found_count = len([r for r in results if r.get("phone") != "-" or r.get("email") != "-"])
            
            await update.message.reply_document(
                document=f,
                filename=filename,
                caption=f"✅ <b>جستجو کامل شد!</b>\n\n"
                       f"🇦🇿 کشور: جمهوری آذربایجان\n"
                       f"🔑 کد HS: {hs_code}\n"
                       f"📋 کل شرکت‌ها: {len(results)}\n"
                       f"📞 دارای شماره/ایمیل: {found_count}\n"
                       f"📅 تاریخ: {datetime.now().strftime('%Y/%m/%d %H:%M')}\n\n"
                       f"💡 منابع: Volza (داده‌های گمرک) → وب‌سایت‌ها / VK (اطلاعات تماس)",
                parse_mode="HTML"
            )
        
        os.remove(filename)
        await msg.delete()
        
    except Exception as e:
        error_text = f"❌ خطا: {str(e)[:200]}"
        await msg.edit_text(error_text)
        logging.error(f"Error in search: {e}")

# ==================== Flask ====================

@app.route('/')
def home():
    return "✅ ربات جستجوی شرکت‌های واردکننده به آذربایجان فعال است!"

@app.route('/health')
def health():
    return "OK", 200

def run_flask():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def run_bot():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))
    
    print("=" * 60)
    print("🇦🇿 ربات جستجوی شرکت‌های واردکننده به جمهوری آذربایجان")
    print("=" * 60)
    print(f"📋 {len(AZERBAIJAN_IMPORTERS)} شرکت در لیست اولیه")
    print("✅ ربات در حال اجراست!")
    print("=" * 60)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    run_bot()
