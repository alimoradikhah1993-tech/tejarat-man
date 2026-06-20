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

TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set!")

app = Flask(__name__)

# ==================== کلمات کلیدی پیش‌فرض ====================
DEFAULT_KEYWORDS_RU = [
    "добавки для бетона",
    "химия для строительства",
    "цемент добавки",
    "пластификатор бетона",
    "суперпластификатор",
    "ускоритель твердения",
    "гидрофобизатор"
]

DEFAULT_KEYWORDS_EN = [
    "concrete additives",
    "cement additives",
    "construction chemicals",
    "concrete admixtures",
    "superplasticizer",
    "building materials",
    "chemical construction"
]

# ==================== توابع جستجو ====================
async def search_vk(keywords: list, country: str) -> list:
    """جستجوی شرکت‌ها در VK با کلمات کلیدی"""
    results = []
    
    # تنظیم کد کشور برای جستجو
    country_code = "az" if country == "Azerbaijan" else "ru"
    
    async with aiohttp.ClientSession() as session:
        for keyword in keywords:
            # جستجو در VK با کلمه کلیدی
            search_url = f"https://vk.com/search?c%5Bq%5D={keyword}&c%5Bsection%5D=groups"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            
            try:
                async with session.get(search_url, headers=headers, timeout=15) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, "html.parser")
                        
                        # پیدا کردن گروه‌ها و صفحات شرکت‌ها
                        group_links = soup.find_all('a', href=re.compile(r'/club\d+|/public\d+'))
                        
                        for link in group_links[:5]:  # حداکثر ۵ نتیجه از هر جستجو
                            if link.get('href'):
                                group_url = f"https://vk.com{link.get('href')}"
                                company_info = await extract_vk_company_info(group_url, country)
                                if company_info:
                                    results.append(company_info)
                                await asyncio.sleep(1)
            except Exception as e:
                logging.warning(f"Error in VK search for {keyword}: {e}")
            
            await asyncio.sleep(2)
    
    return results

async def extract_vk_company_info(url: str, country: str) -> dict:
    """استخراج اطلاعات شرکت از صفحه VK"""
    try:
        async with aiohttp.ClientSession() as session:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            async with session.get(url, headers=headers, timeout=15) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, "html.parser")
                    text = soup.get_text()
                    
                    # استخراج نام
                    name_match = re.search(r'<title>(.*?)<\/title>', html)
                    name = name_match.group(1) if name_match else "Unknown"
                    name = name.replace('ВКонтакте', '').strip()
                    
                    # شماره تلفن (برای روسیه و آذربایجان)
                    phone_patterns = []
                    if country == "Russia":
                        phone_patterns = [
                            r'\+7\s*\(?\d{3}\)?\s*\d{3}[\s-]?\d{2}[\s-]?\d{2}',
                            r'8\s*\(?\d{3}\)?\s*\d{3}[\s-]?\d{2}[\s-]?\d{2}',
                            r'\+7\s*\d{10}',
                        ]
                    else:  # Azerbaijan
                        phone_patterns = [
                            r'\+994\s*\(?\d{2}\)?\s*\d{3}[\s-]?\d{2}[\s-]?\d{2}',
                            r'0[5-9]\d{8}',
                            r'\+994\s*\d{9}',
                            r'0[12]\d{8}',
                        ]
                    
                    phone = None
                    for pattern in phone_patterns:
                        match = re.search(pattern, text)
                        if match:
                            phone = match.group()
                            break
                    
                    # ایمیل
                    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
                    email_match = re.search(email_pattern, text)
                    email = email_match.group() if email_match else None
                    
                    # تشخیص نقش (واردکننده یا توزیع‌کننده)
                    role = "Unknown"
                    if any(word in text.lower() for word in ["импорт", "импортер", "закупка", "importer", "import"]):
                        role = "Importer"
                    elif any(word in text.lower() for word in ["дистрибьютор", "поставщик", "опт", "distributor", "supplier"]):
                        role = "Distributor"
                    
                    if phone or email:
                        return {
                            "name": name[:100].strip(),
                            "phone": phone or "-",
                            "email": email or "-",
                            "website": url,
                            "role": role,
                            "source": "VK",
                            "country": country
                        }
    except Exception as e:
        logging.warning(f"Error extracting VK info: {e}")
    return None

async def search_linkedin(keywords: list, country: str) -> list:
    """جستجوی شرکت‌ها در LinkedIn با کلمات کلیدی"""
    results = []
    
    country_name = "Azerbaijan" if country == "Azerbaijan" else "Russia"
    
    async with aiohttp.ClientSession() as session:
        for keyword in keywords:
            search_url = f"https://www.linkedin.com/search/results/companies/?keywords={keyword}%20{country_name}"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            
            try:
                async with session.get(search_url, headers=headers, timeout=15) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, "html.parser")
                        
                        # پیدا کردن شرکت‌ها
                        company_cards = soup.find_all('div', {'class': 'entity-result'})
                        
                        for card in company_cards[:5]:
                            name_tag = card.find('span', {'class': 'entity-result__title-text'})
                            if name_tag:
                                name = name_tag.get_text().strip()
                                link_tag = card.find('a', href=re.compile(r'/company/'))
                                website = f"https://linkedin.com{link_tag.get('href')}" if link_tag else None
                                
                                # تلاش برای پیدا کردن اطلاعات تماس
                                phone = None
                                email = None
                                text = card.get_text()
                                
                                # شماره تلفن
                                phone_patterns = []
                                if country == "Russia":
                                    phone_patterns = [r'\+7\s*\(?\d{3}\)?\s*\d{3}[\s-]?\d{2}[\s-]?\d{2}', r'8\s*\(?\d{3}\)?\s*\d{3}[\s-]?\d{2}[\s-]?\d{2}']
                                else:
                                    phone_patterns = [r'\+994\s*\(?\d{2}\)?\s*\d{3}[\s-]?\d{2}[\s-]?\d{2}', r'0[5-9]\d{8}']
                                
                                for pattern in phone_patterns:
                                    match = re.search(pattern, text)
                                    if match:
                                        phone = match.group()
                                        break
                                
                                email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
                                email_match = re.search(email_pattern, text)
                                email = email_match.group() if email_match else None
                                
                                if name and name != "LinkedIn":
                                    results.append({
                                        "name": name[:100].strip(),
                                        "phone": phone or "-",
                                        "email": email or "-",
                                        "website": website or "-",
                                        "role": "Unknown",
                                        "source": "LinkedIn",
                                        "country": country
                                    })
                                await asyncio.sleep(1)
            except Exception as e:
                logging.warning(f"Error in LinkedIn search: {e}")
            
            await asyncio.sleep(2)
    
    return results

# ==================== هندلرهای ربات ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # نمایش کلمات کلیدی پیش‌فرض
    keywords_ru = "\n".join([f"   • {kw}" for kw in DEFAULT_KEYWORDS_RU])
    keywords_en = "\n".join([f"   • {kw}" for kw in DEFAULT_KEYWORDS_EN])
    
    await update.message.reply_text(
        f"👋 سلام! من ربات جستجوی شرکت‌های واردکننده و توزیع‌کننده هستم.\n\n"
        f"📌 کد HS کالای خود را وارد کنید.\n"
        f"✅ مثال: 3824400000\n\n"
        f"🔍 <b>کلمات کلیدی پیش‌فرض (روسی - برای VK):</b>\n{keywords_ru}\n\n"
        f"🔍 <b>کلمات کلیدی پیش‌فرض (انگلیسی - برای LinkedIn):</b>\n{keywords_en}\n\n"
        f"💡 اگر می‌خواهید کلمات کلیدی خود را وارد کنید، بعد از کد HS بنویسید.\n"
        f"مثال: 3824400000 افزودنی بتن فوق روان کننده\n\n"
        f"🎯 اگر کلمه‌ای وارد نکنید، از کلمات پیش‌فرض استفاده می‌شود.\n"
        f"🇦🇿 اولویت: آذربایجان 🇦🇿 و سپس روسیه 🇷🇺\n"
        f"📌 منابع: VK و LinkedIn",
        parse_mode="HTML"
    )

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip()
    
    # تجزیه ورودی: کد HS و کلمات کلیدی (اختیاری)
    parts = user_input.split(maxsplit=1)
    hs_code = parts[0]
    custom_keywords = parts[1] if len(parts) > 1 else None
    
    if not hs_code or not hs_code.isdigit() or len(hs_code) < 6:
        await update.message.reply_text(
            "❌ لطفاً یک کد HS معتبر وارد کنید.\n"
            "✅ مثال: 3824400000"
        )
        return
    
    # تعیین کلمات کلیدی
    keywords_ru = DEFAULT_KEYWORDS_RU.copy()
    keywords_en = DEFAULT_KEYWORDS_EN.copy()
    
    if custom_keywords:
        # اگر کاربر کلمات کلیدی خود را وارد کرده، از آنها استفاده کن
        custom_list = [kw.strip() for kw in custom_keywords.split(',')]
        keywords_ru = custom_list.copy()
        keywords_en = custom_list.copy()
        await update.message.reply_text(
            f"✅ از کلمات کلیدی شما استفاده می‌شود:\n"
            f"📌 {', '.join(custom_list[:5])}{' ...' if len(custom_list) > 5 else ''}"
        )
    
    msg = await update.message.reply_text(
        f"🔍 در حال جستجوی شرکت‌ها برای کد HS: {hs_code}\n"
        f"🌍 کشورها: آذربایجان 🇦🇿 و روسیه 🇷🇺\n"
        f"🔑 کلمات کلیدی: {', '.join(keywords_ru[:3])}{' ...' if len(keywords_ru) > 3 else ''}\n"
        f"⏳ این فرآیند ممکن است ۳-۵ دقیقه طول بکشد..."
    )
    
    try:
        all_companies = []
        
        # ===== جستجو در VK =====
        await msg.edit_text("🔍 مرحله ۱: جستجو در VK (آذربایجان)...")
        vk_az = await search_vk(keywords_ru, "Azerbaijan")
        all_companies.extend(vk_az)
        
        await msg.edit_text("🔍 مرحله ۲: جستجو در VK (روسیه)...")
        vk_ru = await search_vk(keywords_ru, "Russia")
        all_companies.extend(vk_ru)
        
        # ===== جستجو در LinkedIn =====
        await msg.edit_text("🔍 مرحله ۳: جستجو در LinkedIn (آذربایجان)...")
        ln_az = await search_linkedin(keywords_en, "Azerbaijan")
        all_companies.extend(ln_az)
        
        await msg.edit_text("🔍 مرحله ۴: جستجو در LinkedIn (روسیه)...")
        ln_ru = await search_linkedin(keywords_en, "Russia")
        all_companies.extend(ln_ru)
        
        # ===== حذف تکراری‌ها =====
        seen = set()
        unique_companies = []
        for company in all_companies:
            key = f"{company['name']}_{company['phone']}"
            if key not in seen:
                seen.add(key)
                unique_companies.append(company)
        
        if not unique_companies:
            await msg.edit_text(
                f"😕 هیچ شرکتی پیدا نشد.\n\n"
                f"💡 نکات:\n"
                f"• سعی کنید کلمات کلیدی دیگری استفاده کنید\n"
                f"• ممکن است شرکت‌ها اطلاعات تماس عمومی نداشته باشند"
            )
            return
        
        # ===== ایجاد فایل اکسل =====
        df = pd.DataFrame(unique_companies)
        df = df.fillna("-")
        
        # مرتب‌سازی: اول آذربایجان، سپس روسیه
        df['country_order'] = df['country'].apply(lambda x: 0 if x == 'Azerbaijan' else 1)
        df = df.sort_values('country_order')
        df = df.drop('country_order', axis=1)
        
        filename = f"شرکتهای_واردکننده_{hs_code}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name="شرکت‌ها")
            
            info_df = pd.DataFrame({
                'اطلاعات': [
                    f'کد HS: {hs_code}',
                    f'تاریخ جستجو: {datetime.now().strftime("%Y/%m/%d %H:%M")}',
                    f'تعداد کل شرکت‌ها: {len(unique_companies)}',
                    f'منابع: VK و LinkedIn',
                    f'کلمات کلیدی: {", ".join(keywords_ru[:5])}...',
                    f'کشورها: آذربایجان و روسیه'
                ]
            })
            info_df.to_excel(writer, index=False, sheet_name="اطلاعات")
        
        with open(filename, 'rb') as f:
            found_count = len([c for c in unique_companies if c.get('phone') != '-' or c.get('email') != '-'])
            
            await update.message.reply_document(
                document=f,
                filename=filename,
                caption=f"✅ <b>جستجو کامل شد!</b>\n\n"
                       f"🔑 کد HS: {hs_code}\n"
                       f"📋 کل شرکت‌ها: {len(unique_companies)}\n"
                       f"📞 دارای شماره/ایمیل: {found_count}\n"
                       f"📅 تاریخ: {datetime.now().strftime('%Y/%m/%d %H:%M')}\n\n"
                       f"📌 منابع: VK و LinkedIn\n"
                       f"🌍 کشورها: آذربایجان 🇦🇿 و روسیه 🇷🇺",
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
    return "✅ ربات جستجوی شرکت‌های واردکننده فعال است!"

@app.route('/health')
def health():
    return "OK", 200

# ==================== اجرا ====================
def run_flask():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def run_bot():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))
    
    print("=" * 60)
    print("🤖 ربات جستجوی شرکت‌های واردکننده و توزیع‌کننده")
    print("=" * 60)
    print("🌍 کشورها: آذربایجان 🇦🇿 و روسیه 🇷🇺")
    print("📌 منابع: VK و LinkedIn")
    print(f"🔑 {len(DEFAULT_KEYWORDS_RU)} کلمه کلیدی پیش‌فرض")
    print("=" * 60)
    print("✅ ربات در حال اجراست!")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    run_bot()
