import os
import re
import pandas as pd
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import logging
import aiohttp
from bs4 import BeautifulSoup
import asyncio

logging.basicConfig(level=logging.INFO)
TOKEN = os.environ.get("TELEGRAM_TOKEN")

# ==================== جستجو در VK (بدون API) ====================
async def search_vk(company_type: str, country: str) -> list:
    """
    جستجوی شرکت‌ها در VK با استفاده از جستجوی گوگل (بدون نیاز به API)
    company_type: 'importer' یا 'distributor'
    country: 'Azerbaijan' یا 'Russia'
    """
    results = []
    
    # کلمات کلیدی بر اساس نوع شرکت و کشور
    keywords = {
        "Azerbaijan": {
            "importer": ["импортер", "импорт", "закупка"],
            "distributor": ["дистрибьютор", "поставщик", "опт"]
        },
        "Russia": {
            "importer": ["импортер", "импорт", "закупка"],
            "distributor": ["дистрибьютор", "поставщик", "опт"]
        }
    }
    
    # جستجوی شرکت‌های مرتبط با کد 3824400000
    search_terms = [
        f'добавки для бетона',
        f'химия для строительства',
        f'цемент добавки',
        f'строительные материалы'
    ]
    
    async with aiohttp.ClientSession() as session:
        for term in search_terms:
            for role in keywords[country][company_type]:
                # جستجوی عمومی در گوگل با محدودیت دامنه VK
                search_url = f"https://html.duckduckgo.com/html/?q=site:vk.com+{term}+{role}+{country}"
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                
                try:
                    async with session.get(search_url, headers=headers, timeout=15) as response:
                        if response.status == 200:
                            html = await response.text()
                            soup = BeautifulSoup(html, "html.parser")
                            
                            # استخراج نتایج
                            for result in soup.find_all('a', {'class': 'result__a'}):
                                link = result.get('href')
                                if link and 'vk.com' in link:
                                    # باز کردن صفحه VK برای استخراج اطلاعات
                                    company_info = await extract_vk_page_info(link)
                                    if company_info:
                                        results.append(company_info)
                                    await asyncio.sleep(1)  # جلوگیری از مسدود شدن
                except Exception as e:
                    logging.warning(f"Error in VK search: {e}")
                
                await asyncio.sleep(2)  # بین هر جستجو
    
    return results

async def extract_vk_page_info(url: str) -> dict:
    """
    استخراج اطلاعات از صفحه VK
    """
    try:
        async with aiohttp.ClientSession() as session:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            async with session.get(url, headers=headers, timeout=15) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, "html.parser")
                    text = soup.get_text()
                    
                    # استخراج نام شرکت
                    name_match = re.search(r'<title>(.*?)<\/title>', html)
                    name = name_match.group(1) if name_match else "Unknown"
                    
                    # استخراج شماره تلفن (الگوهای روسی و آذربایجانی)
                    phone_patterns = [
                        r'\+7\s*\(?\d{3}\)?\s*\d{3}[\s-]?\d{2}[\s-]?\d{2}',  # روسیه
                        r'\+994\s*\(?\d{2}\)?\s*\d{3}[\s-]?\d{2}[\s-]?\d{2}',  # آذربایجان
                        r'8\s*\(?\d{3}\)?\s*\d{3}[\s-]?\d{2}[\s-]?\d{2}',  # روسیه (محلی)
                        r'0[5-9]\d{8}',  # موبایل آذربایجان
                    ]
                    phone = None
                    for pattern in phone_patterns:
                        match = re.search(pattern, text)
                        if match:
                            phone = match.group()
                            break
                    
                    # استخراج ایمیل
                    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
                    email_match = re.search(email_pattern, text)
                    email = email_match.group() if email_match else None
                    
                    # استخراج آدرس
                    address_patterns = [
                        r'[А-Яа-я\s]+,\s*[А-Яа-я\s]+,\s*ул\.[А-Яа-я\s]+,\s*\d+',
                        r'[A-Za-z\s]+,\s*[A-Za-z\s]+,\s*[A-Za-z\s]+,\s*\d+'
                    ]
                    address = None
                    for pattern in address_patterns:
                        match = re.search(pattern, text)
                        if match:
                            address = match.group()
                            break
                    
                    # تشخیص اینکه شرکت واردکننده است یا توزیع‌کننده
                    role = "Unknown"
                    if any(word in text.lower() for word in ["импорт", "импортер", "закупка"]):
                        role = "Importer"
                    elif any(word in text.lower() for word in ["дистрибьютор", "поставщик", "опт"]):
                        role = "Distributor"
                    
                    # استخراج محصولات
                    product_keywords = ["бетон", "цемент", "добавки", "construction", "concrete", "cement", "additive"]
                    products = []
                    for p in product_keywords:
                        if p.lower() in text.lower():
                            products.append(p)
                    
                    if phone or email:
                        return {
                            "name": name[:100].strip(),
                            "phone": phone or "-",
                            "email": email or "-",
                            "address": address or "-",
                            "website": url,
                            "role": role,
                            "products": ", ".join(products) if products else "-",
                            "source": "VK"
                        }
    except Exception as e:
        logging.warning(f"Error extracting VK info: {e}")
    return None

# ==================== جستجو در LinkedIn (بدون API) ====================
async def search_linkedin(company_type: str, country: str) -> list:
    """
    جستجوی شرکت‌ها در LinkedIn با استفاده از جستجوی گوگل (بدون نیاز به API)
    """
    results = []
    
    role_keywords = {
        "importer": ["importer", "import", "procurement", "purchasing"],
        "distributor": ["distributor", "supplier", "wholesale", "dealer"]
    }
    
    country_keywords = {
        "Azerbaijan": ["Azerbaijan", "Baku", "AZ"],
        "Russia": ["Russia", "Moscow", "RU"]
    }
    
    async with aiohttp.ClientSession() as session:
        for country_key in country_keywords[country]:
            for role in role_keywords[company_type]:
                search_url = f"https://html.duckduckgo.com/html/?q=site:linkedin.com+{country_key}+{role}+concrete+additive+3824400000"
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                
                try:
                    async with session.get(search_url, headers=headers, timeout=15) as response:
                        if response.status == 200:
                            html = await response.text()
                            soup = BeautifulSoup(html, "html.parser")
                            
                            for result in soup.find_all('a', {'class': 'result__a'}):
                                link = result.get('href')
                                if link and ('linkedin.com/company' in link or 'linkedin.com/in' in link):
                                    # استخراج اطلاعات
                                    company_info = await extract_linkedin_info(link)
                                    if company_info:
                                        results.append(company_info)
                                    await asyncio.sleep(1)
                except Exception as e:
                    logging.warning(f"Error in LinkedIn search: {e}")
                
                await asyncio.sleep(2)
    
    return results

async def extract_linkedin_info(url: str) -> dict:
    """
    استخراج اطلاعات از صفحه LinkedIn
    """
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
                    
                    # استخراج اطلاعات تماس (الگوهای روسی و آذربایجانی)
                    phone_patterns = [
                        r'\+7\s*\(?\d{3}\)?\s*\d{3}[\s-]?\d{2}[\s-]?\d{2}',
                        r'\+994\s*\(?\d{2}\)?\s*\d{3}[\s-]?\d{2}[\s-]?\d{2}',
                        r'8\s*\(?\d{3}\)?\s*\d{3}[\s-]?\d{2}[\s-]?\d{2}',
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
                    
                    # تشخیص نقش
                    role = "Unknown"
                    if any(word in text.lower() for word in ["importer", "import", "procurement", "purchasing"]):
                        role = "Importer"
                    elif any(word in text.lower() for word in ["distributor", "supplier", "wholesale"]):
                        role = "Distributor"
                    
                    if phone or email:
                        return {
                            "name": name[:100].strip(),
                            "phone": phone or "-",
                            "email": email or "-",
                            "address": "-",
                            "website": url,
                            "role": role,
                            "products": "-",
                            "source": "LinkedIn"
                        }
    except Exception as e:
        logging.warning(f"Error extracting LinkedIn info: {e}")
    return None

# ==================== هندلر ربات ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 سلام! من ربات جستجوی شرکت‌های واردکننده و توزیع‌کننده در روسیه و آذربایجان هستم.\n\n"
        "📌 کد HS کالای خود را وارد کنید.\n"
        "✅ مثال: 3824400000\n\n"
        "🔍 منابع جستجو:\n"
        "1️⃣ VK (اولویت اول)\n"
        "2️⃣ LinkedIn (اولویت دوم)\n\n"
        "🎯 فقط شرکت‌های واردکننده و توزیع‌کننده جستجو می‌شوند."
    )

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    hs_code = update.message.text.strip()
    
    if not hs_code or not hs_code.isdigit() or len(hs_code) < 6:
        await update.message.reply_text("❌ لطفاً یک کد HS معتبر وارد کنید.")
        return
    
    msg = await update.message.reply_text(
        f"🔍 در حال جستجوی شرکت‌های واردکننده و توزیع‌کننده برای کد HS: {hs_code}\n"
        f"🇦🇿 اولویت: جمهوری آذربایجان\n"
        f"🇷🇺 سپس: روسیه\n"
        f"⏳ این فرآیند ممکن است ۳-۵ دقیقه طول بکشد...\n\n"
        f"📌 منابع: VK و LinkedIn"
    )
    
    try:
        all_companies = []
        
        # جستجو در VK
        await msg.edit_text(
            f"🔍 مرحله ۱: جستجو در VK (اولویت اول)...\n"
            f"🇦🇿 آذربایجان\n"
            f"⏳ در حال جستجو..."
        )
        
        vk_az_importers = await search_vk("importer", "Azerbaijan")
        vk_az_distributors = await search_vk("distributor", "Azerbaijan")
        
        await msg.edit_text(
            f"🔍 مرحله ۱: جستجو در VK (اولویت اول)...\n"
            f"🇷🇺 روسیه\n"
            f"⏳ در حال جستجو..."
        )
        
        vk_ru_importers = await search_vk("importer", "Russia")
        vk_ru_distributors = await search_vk("distributor", "Russia")
        
        all_companies.extend(vk_az_importers)
        all_companies.extend(vk_az_distributors)
        all_companies.extend(vk_ru_importers)
        all_companies.extend(vk_ru_distributors)
        
        # جستجو در LinkedIn
        await msg.edit_text(
            f"🔍 مرحله ۲: جستجو در LinkedIn...\n"
            f"⏳ در حال جستجو..."
        )
        
        ln_az_importers = await search_linkedin("importer", "Azerbaijan")
        ln_az_distributors = await search_linkedin("distributor", "Azerbaijan")
        ln_ru_importers = await search_linkedin("importer", "Russia")
        ln_ru_distributors = await search_linkedin("distributor", "Russia")
        
        all_companies.extend(ln_az_importers)
        all_companies.extend(ln_az_distributors)
        all_companies.extend(ln_ru_importers)
        all_companies.extend(ln_ru_distributors)
        
        # حذف موارد تکراری
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
                f"• از کلمات کلیدی دقیق‌تر استفاده کنید\n"
                f"• ممکن است شرکت‌ها اطلاعات تماس عمومی نداشته باشند"
            )
            return
        
        # ایجاد فایل اکسل
        df = pd.DataFrame(unique_companies)
        
        # مرتب‌سازی: اول آذربایجان، سپس روسیه
        df['country'] = df['website'].apply(
            lambda x: 'Azerbaijan' if 'az' in str(x).lower() or 'azerbaijan' in str(x).lower() else 'Russia'
        )
        df = df.sort_values('country', ascending=True)
        df = df.drop('country', axis=1)
        
        df = df.fillna("-")
        
        filename = f"شرکتهای_واردکننده_توزیعکننده_{hs_code}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name="شرکت‌ها")
            
            # برگه اطلاعات
            info_df = pd.DataFrame({
                'اطلاعات': [
                    f'کد HS: {hs_code}',
                    f'تاریخ جستجو: {datetime.now().strftime("%Y/%m/%d %H:%M")}',
                    f'تعداد کل شرکت‌ها: {len(unique_companies)}',
                    f'منابع جستجو: VK (روسی و آذربایجانی)، LinkedIn',
                    f'نوع شرکت‌ها: واردکننده و توزیع‌کننده',
                    f'اولویت: آذربایجان و سپس روسیه'
                ]
            })
            info_df.to_excel(writer, index=False, sheet_name="اطلاعات")
        
        # ارسال فایل
        with open(filename, 'rb') as f:
            await update.message.reply_document(
                document=f,
                filename=filename,
                caption=f"✅ <b>جستجو کامل شد!</b>\n\n"
                       f"🔑 کد HS: {hs_code}\n"
                       f"📋 کل شرکت‌ها: {len(unique_companies)}\n"
                       f"📞 دارای شماره/ایمیل: {len([c for c in unique_companies if c.get('phone') != '-' or c.get('email') != '-'])}\n"
                       f"📅 تاریخ: {datetime.now().strftime('%Y/%m/%d %H:%M')}\n\n"
                       f"📌 منابع: VK و LinkedIn (جستجوی عمومی بدون API)\n"
                       f"🎯 فقط واردکنندگان و توزیع‌کنندگان",
                parse_mode="HTML"
            )
        
        os.remove(filename)
        await msg.delete()
        
    except Exception as e:
        error_text = f"❌ خطا: {str(e)[:200]}"
        await msg.edit_text(error_text)
        logging.error(f"Error in search: {e}")

# ==================== اجرا ====================
def run_bot():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))
    
    print("=" * 60)
    print("🤖 ربات جستجوی شرکت‌های واردکننده و توزیع‌کننده")
    print("=" * 60)
    print("🇦🇿 اولویت: جمهوری آذربایجان")
    print("🇷🇺 سپس: روسیه")
    print("📌 منابع: VK (بدون API) و LinkedIn (بدون API)")
    print("🎯 فقط واردکنندگان و توزیع‌کنندگان")
    print("=" * 60)
    print("✅ ربات در حال اجراست!")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    run_bot()
