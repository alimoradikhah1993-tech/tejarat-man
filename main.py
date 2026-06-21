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

# ==================== کلمات کلیدی برای جستجو ====================
# کلمات کلیدی به روسی برای VK
KEYWORDS_RU = [
    "добавки для бетона",
    "пластификатор бетона",
    "суперпластификатор для бетона",
    "ремонт бетона",
    "клей для бетона",
    "грунтовка для бетона",
    "гидроизоляция бетона",
    "цементный клей",
    "ремонтная смесь для бетона",
    "добавки в бетон",
    "ускоритель твердения бетона",
    "замедлитель схватывания бетона",
    "армирующее волокно для бетона",
    "пропитка для бетона",
    "герметик для бетона"
]

# کلمات کلیدی به انگلیسی برای LinkedIn
KEYWORDS_EN = [
    "concrete admixtures",
    "concrete plasticizer",
    "superplasticizer",
    "concrete repair",
    "concrete adhesive",
    "concrete primer",
    "concrete waterproofing",
    "concrete additives",
    "cementitious grout",
    "concrete chemicals",
    "concrete hardening accelerator",
    "concrete set retarder",
    "concrete fiber reinforcement",
    "concrete sealer",
    "concrete sealant"
]

# ==================== توابع جستجو ====================
async def search_vk(keywords: list) -> list:
    """جستجوی شرکت‌ها در VK با کلمات کلیدی (فقط آذربایجان)"""
    results = []
    
    async with aiohttp.ClientSession() as session:
        for keyword in keywords:
            # جستجو در VK با کلمه کلیدی - محدود به آذربایجان
            search_url = f"https://vk.com/search?c%5Bq%5D={keyword}&c%5Bsection%5D=groups&c%5Bcountry%5D=az"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "ru-RU,ru;q=0.9"
            }
            
            try:
                async with session.get(search_url, headers=headers, timeout=15) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, "html.parser")
                        
                        # پیدا کردن گروه‌ها و صفحات شرکت‌ها
                        group_links = soup.find_all('a', href=re.compile(r'/club\d+|/public\d+'))
                        
                        for link in group_links[:10]:  # افزایش به ۱۰ نتیجه
                            if link.get('href'):
                                group_url = f"https://vk.com{link.get('href')}"
                                company_info = await extract_vk_company_info(group_url)
                                if company_info:
                                    results.append(company_info)
                                await asyncio.sleep(0.5)
            except Exception as e:
                logging.warning(f"Error in VK search for {keyword}: {e}")
            
            await asyncio.sleep(1)
    
    return results

async def extract_vk_company_info(url: str) -> dict:
    """استخراج اطلاعات شرکت از صفحه VK (فقط آذربایجان)"""
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "ru-RU,ru;q=0.9"
            }
            async with session.get(url, headers=headers, timeout=15) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, "html.parser")
                    text = soup.get_text()
                    
                    # استخراج نام
                    name_match = re.search(r'<title>(.*?)<\/title>', html)
                    name = name_match.group(1) if name_match else "Unknown"
                    name = name.replace('ВКонтакте', '').replace('VK', '').strip()
                    
                    # شماره تلفن آذربایجان
                    phone_patterns = [
                        r'\+994\s*\(?\d{2}\)?\s*\d{3}[\s-]?\d{2}[\s-]?\d{2}',
                        r'\+994\s*\d{9}',
                        r'0[5-9]\d{8}',
                        r'0[12]\d{8}',
                        r'\(?0[5-9]\)?\s*\d{3}[\s-]?\d{2}[\s-]?\d{2}'
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
                    
                    # حتی اگر شماره یا ایمیل نداشت، شرکت را ذخیره کن
                    if name and name != "Unknown":
                        return {
                            "name": name[:150].strip(),
                            "phone": phone or "-",
                            "email": email or "-",
                            "website": url,
                            "role": role,
                            "source": "VK",
                            "country": "Azerbaijan"
                        }
    except Exception as e:
        logging.warning(f"Error extracting VK info: {e}")
    return None

async def search_linkedin(keywords: list) -> list:
    """جستجوی شرکت‌ها در LinkedIn با کلمات کلیدی (فقط آذربایجان)"""
    results = []
    
    async with aiohttp.ClientSession() as session:
        for keyword in keywords:
            # جستجو در LinkedIn با محدودیت آذربایجان
            search_url = f"https://www.linkedin.com/search/results/companies/?keywords={keyword}%20Azerbaijan"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "en-US,en;q=0.9"
            }
            
            try:
                async with session.get(search_url, headers=headers, timeout=15) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, "html.parser")
                        
                        # پیدا کردن شرکت‌ها
                        company_cards = soup.find_all('div', {'class': 'entity-result'})
                        
                        for card in company_cards[:10]:  # افزایش به ۱۰ نتیجه
                            name_tag = card.find('span', {'class': 'entity-result__title-text'})
                            if name_tag:
                                name = name_tag.get_text().strip()
                                link_tag = card.find('a', href=re.compile(r'/company/'))
                                website = f"https://linkedin.com{link_tag.get('href')}" if link_tag else None
                                
                                # تلاش برای پیدا کردن اطلاعات تماس
                                phone = None
                                email = None
                                text = card.get_text()
                                
                                # شماره تلفن آذربایجان
                                phone_patterns = [
                                    r'\+994\s*\(?\d{2}\)?\s*\d{3}[\s-]?\d{2}[\s-]?\d{2}',
                                    r'\+994\s*\d{9}',
                                    r'0[5-9]\d{8}',
                                    r'0[12]\d{8}'
                                ]
                                
                                for pattern in phone_patterns:
                                    match = re.search(pattern, text)
                                    if match:
                                        phone = match.group()
                                        break
                                
                                email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
                                email_match = re.search(email_pattern, text)
                                email = email_match.group() if email_match else None
                                
                                # حتی اگر شماره یا ایمیل نداشت، شرکت را ذخیره کن
                                if name and name != "LinkedIn" and name != "Sign Up":
                                    results.append({
                                        "name": name[:150].strip(),
                                        "phone": phone or "-",
                                        "email": email or "-",
                                        "website": website or "-",
                                        "role": "Unknown",
                                        "source": "LinkedIn",
                                        "country": "Azerbaijan"
                                    })
                                await asyncio.sleep(0.5)
            except Exception as e:
                logging.warning(f"Error in LinkedIn search: {e}")
            
            await asyncio.sleep(1)
    
    return results

# ==================== هندلرهای ربات ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # نمایش کلمات کلیدی
    keywords_ru = "\n".join([f"   • {kw}" for kw in KEYWORDS_RU[:10]])
    keywords_en = "\n".join([f"   • {kw}" for kw in KEYWORDS_EN[:10]])
    
    await update.message.reply_text(
        f"👋 سلام! من ربات جستجوی شرکت‌های فعال در صنعت بتن در آذربایجان هستم.\n\n"
        f"🏗️ <b>موارد جستجو:</b>\n"
        f"• روان کننده بتن\n"
        f"• ترمیم بتن\n"
        f"• چسب بتن\n"
        f"• گروت (دوغاب سیمانی)\n"
        f"• عایق بتن\n"
        f"• افزودنی‌های بتن\n\n"
        f"🔍 <b>کلمات کلیدی (روسی - VK):</b>\n{keywords_ru}\n\n"
        f"🔍 <b>کلمات کلیدی (انگلیسی - LinkedIn):</b>\n{keywords_en}\n\n"
        f"🇦🇿 <b>کشور: جمهوری آذربایجان</b>\n"
        f"📌 منابع: VK و LinkedIn\n\n"
        f"💡 برای شروع جستجو، هر پیامی ارسال کنید (مثلاً «جستجو»).\n"
        f"⏳ زمان جستجو: حدود ۳-۵ دقیقه",
        parse_mode="HTML"
    )

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text(
        f"🔍 شروع جستجوی شرکت‌های فعال در صنعت بتن در آذربایجان...\n\n"
        f"🏗️ <b>موارد جستجو:</b>\n"
        f"• روان کننده بتن\n"
        f"• ترمیم بتن\n"
        f"• چسب بتن\n"
        f"• گروت (دوغاب سیمانی)\n"
        f"• عایق بتن\n"
        f"• افزودنی‌های بتن\n\n"
        f"🔑 <b>تعداد کلمات کلیدی:</b> {len(KEYWORDS_RU)} (روسی) + {len(KEYWORDS_EN)} (انگلیسی)\n"
        f"🌍 <b>کشور:</b> آذربایجان 🇦🇿\n"
        f"⏳ این فرآیند ممکن است ۳-۵ دقیقه طول بکشد...",
        parse_mode="HTML"
    )
    
    try:
        all_companies = []
        
        # ===== جستجو در VK =====
        await msg.edit_text(
            f"🔍 مرحله ۱: جستجو در VK (آذربایجان)...\n"
            f"🔑 {len(KEYWORDS_RU)} کلمه کلیدی روسی"
        )
        vk_companies = await search_vk(KEYWORDS_RU)
        all_companies.extend(vk_companies)
        logging.info(f"VK: {len(vk_companies)} شرکت پیدا شد")
        
        # ===== جستجو در LinkedIn =====
        await msg.edit_text(
            f"🔍 مرحله ۲: جستجو در LinkedIn (آذربایجان)...\n"
            f"🔑 {len(KEYWORDS_EN)} کلمه کلیدی انگلیسی"
        )
        ln_companies = await search_linkedin(KEYWORDS_EN)
        all_companies.extend(ln_companies)
        logging.info(f"LinkedIn: {len(ln_companies)} شرکت پیدا شد")
        
        # ===== حذف تکراری‌ها =====
        seen_names = set()
        seen_urls = set()
        unique_companies = []
        
        for company in all_companies:
            name_key = company['name'].lower().strip()
            url_key = company['website'] if company['website'] != '-' else name_key
            
            # حذف شرکت‌های تکراری بر اساس نام و وبسایت
            if name_key not in seen_names and url_key not in seen_urls:
                seen_names.add(name_key)
                seen_urls.add(url_key)
                unique_companies.append(company)
        
        logging.info(f"کل شرکت‌ها: {len(all_companies)}, پس از حذف تکراری: {len(unique_companies)}")
        
        if not unique_companies:
            await msg.edit_text(
                f"😕 هیچ شرکتی در آذربایجان پیدا نشد.\n\n"
                f"💡 نکات:\n"
                f"• ممکن است شرکت‌ها در VK یا LinkedIn حضور نداشته باشند\n"
                f"• سعی کنید دوباره جستجو کنید\n"
                f"• ممکن است نیاز به کلمات کلیدی دقیق‌تر باشد"
            )
            return
        
        # ===== ایجاد فایل اکسل =====
        df = pd.DataFrame(unique_companies)
        df = df.fillna("-")
        
        # مرتب‌سازی بر اساس منبع و نقش
        df = df.sort_values(['source', 'role'])
        
        filename = f"شرکتهای_بتن_آذربایجان_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name="شرکت‌های بتن")
            
            # اطلاعات جستجو
            info_data = {
                'اطلاعات': [
                    f'موضوع جستجو: افزودنی‌ها و محصولات بتن',
                    f'تاریخ جستجو: {datetime.now().strftime("%Y/%m/%d %H:%M")}',
                    f'تعداد کل شرکت‌ها: {len(unique_companies)}',
                    f'شرکت‌های VK: {len([c for c in unique_companies if c["source"]=="VK"])}',
                    f'شرکت‌های LinkedIn: {len([c for c in unique_companies if c["source"]=="LinkedIn"])}',
                    f'شرکت‌های دارای شماره: {len([c for c in unique_companies if c["phone"]!="-"])}',
                    f'شرکت‌های دارای ایمیل: {len([c for c in unique_companies if c["email"]!="-"])}',
                    f'کشور: جمهوری آذربایجان',
                    f'منابع: VK و LinkedIn',
                    f'تعداد کلمات کلیدی روسی: {len(KEYWORDS_RU)}',
                    f'تعداد کلمات کلیدی انگلیسی: {len(KEYWORDS_EN)}'
                ]
            }
            info_df = pd.DataFrame(info_data)
            info_df.to_excel(writer, index=False, sheet_name="اطلاعات جستجو")
        
        with open(filename, 'rb') as f:
            # آمار
            total = len(unique_companies)
            vk_count = len([c for c in unique_companies if c["source"] == "VK"])
            ln_count = len([c for c in unique_companies if c["source"] == "LinkedIn"])
            has_phone = len([c for c in unique_companies if c["phone"] != "-"])
            has_email = len([c for c in unique_companies if c["email"] != "-"])
            
            await update.message.reply_document(
                document=f,
                filename=filename,
                caption=f"✅ <b>جستجو کامل شد!</b>\n\n"
                       f"🏗️ <b>صنعت بتن در آذربایجان</b>\n"
                       f"📋 کل شرکت‌ها: {total}\n"
                       f"📌 VK: {vk_count} شرکت\n"
                       f"📌 LinkedIn: {ln_count} شرکت\n"
                       f"📞 دارای شماره تلفن: {has_phone}\n"
                       f"✉️ دارای ایمیل: {has_email}\n"
                       f"📅 تاریخ: {datetime.now().strftime('%Y/%m/%d %H:%M')}\n\n"
                       f"🇦🇿 <b>کشور: جمهوری آذربایجان</b>\n"
                       f"🔑 {len(KEYWORDS_RU)} کلمه کلیدی روسی + {len(KEYWORDS_EN)} کلمه کلیدی انگلیسی",
                parse_mode="HTML"
            )
        
        os.remove(filename)
        await msg.delete()
        
    except Exception as e:
        error_msg = str(e)[:300]
        await msg.edit_text(f"❌ خطا در جستجو: {error_msg}\n\nلطفاً دوباره تلاش کنید.")
        logging.error(f"Error in search: {e}", exc_info=True)

# ==================== Flask Routes ====================
@app.route('/')
def home():
    return "✅ ربات جستجوی شرکت‌های صنعت بتن در آذربایجان فعال است!"

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
    
    print("=" * 70)
    print("🤖 ربات جستجوی شرکت‌های صنعت بتن در آذربایجان")
    print("=" * 70)
    print("🏗️  موضوعات: روان کننده بتن، ترمیم بتن، چسب بتن، گروت، عایق بتن، افزودنی‌ها")
    print("🌍 کشور: جمهوری آذربایجان 🇦🇿")
    print("📌 منابع: VK و LinkedIn")
    print(f"🔑 {len(KEYWORDS_RU)} کلمه کلیدی روسی + {len(KEYWORDS_EN)} کلمه کلیدی انگلیسی")
    print("=" * 70)
    print("✅ ربات در حال اجراست!")
    print("💡 برای شروع جستجو، هر پیامی ارسال کنید")
    print("=" * 70)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    run_bot()
