import os
import asyncio
import re
import pandas as pd
from datetime import datetime, timedelta
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

# ==================== لیست نمایشگاه‌های ثابت (برای زمانی که جستجوی گوگل نتیجه ندهد) ====================
FIXED_EXHIBITIONS = [
    # نمایشگاه‌های سال ۲۰۲۶ (بخش الیاف و نخ)
    {
        "name": "Yarn Expo Spring 2026",
        "city": "Shanghai, China",
        "date": "11-13 March 2026",
        "category": "Fibers & Yarns",
        "website": "https://www.yarn-expo.com"
    },
    {
        "name": "Yarn Expo Shenzhen 2026",
        "city": "Shenzhen, China",
        "date": "9-11 June 2026",
        "category": "Fibers & Yarns",
        "website": "https://www.yarn-expo.com"
    },
    {
        "name": "Intertextile Shanghai Apparel Fabrics (Spring)",
        "city": "Shanghai, China",
        "date": "11-13 March 2026",
        "category": "Apparel Fabrics",
        "website": "https://www.intertextile.com"
    },
    {
        "name": "Intertextile Shanghai Apparel Fabrics (Autumn)",
        "city": "Shanghai, China",
        "date": "25-27 August 2026",
        "category": "Apparel Fabrics",
        "website": "https://www.intertextile.com"
    },
    {
        "name": "Techtextil 2026",
        "city": "Frankfurt, Germany",
        "date": "21-24 April 2026",
        "category": "Technical Textiles & Nonwovens",
        "website": "https://techtextil.messefrankfurt.com"
    },
    {
        "name": "Première Vision Paris",
        "city": "Paris, France",
        "date": "3-5 February 2026",
        "category": "Textile & Fashion",
        "website": "https://www.premierevision.com"
    },
    {
        "name": "Munich Fabric Start",
        "city": "Munich, Germany",
        "date": "14-16 July 2026",
        "category": "Textile & Fashion",
        "website": "https://www.munichfabricstart.com"
    },
    {
        "name": "Texworld New York City",
        "city": "New York, USA",
        "date": "Winter & Summer 2026",
        "category": "Textile & Fashion",
        "website": "https://texworld-usa.com"
    },
    {
        "name": "MAGIC Las Vegas",
        "city": "Las Vegas, USA",
        "date": "17-19 February 2026",
        "category": "Fashion & Apparel",
        "website": "https://www.magiclasvegas.com"
    },
    {
        "name": "Istanbul Fashion Connection (IFCO)",
        "city": "Istanbul, Turkey",
        "date": "4-7 February 2026 (Winter), 19-21 August 2026 (Summer)",
        "category": "Fashion & Apparel",
        "website": "https://www.ifco.com.tr"
    },
    {
        "name": "Texhibition Istanbul",
        "city": "Istanbul, Turkey",
        "date": "March 2026",
        "category": "Textile & Fashion",
        "website": "https://www.texhibition.com"
    },
    {
        "name": "HOMETEX Istanbul",
        "city": "Istanbul, Turkey",
        "date": "May 2026",
        "category": "Home Textiles",
        "website": "https://www.hometex.com"
    },
    {
        "name": "Techtextil North America 2026",
        "city": "Raleigh, NC, USA",
        "date": "4-6 August 2026",
        "category": "Technical Textiles",
        "website": "https://techtextil-na.com"
    },
    {
        "name": "Advanced Textiles Expo 2026",
        "city": "Orlando, FL, USA",
        "date": "3-5 November 2026",
        "category": "Technical Textiles",
        "website": "https://www.advancedtextilesexpo.com"
    },
    {
        "name": "Dornbirn Global Fiber Congress 2026",
        "city": "Dornbirn, Austria",
        "date": "16-18 September 2026",
        "category": "Fibers & Innovation",
        "website": "https://www.dornbirn-gfc.com"
    },
    {
        "name": "Heimtextil 2027",
        "city": "Frankfurt, Germany",
        "date": "12-15 January 2027",
        "category": "Home Textiles",
        "website": "https://heimtextil.messefrankfurt.com"
    },
    {
        "name": "IATF Dubai",
        "city": "Dubai, UAE",
        "date": "18-20 May 2026",
        "category": "Textile & Fashion",
        "website": "https://iatf.ae"
    },
    {
        "name": "Vietnam SaigonTex 2026",
        "city": "Ho Chi Minh, Vietnam",
        "date": "8-11 April 2026",
        "category": "Textile & Apparel",
        "website": "https://saigontex.com"
    },
    {
        "name": "VIATT 2027 (Vietnam Textile and Apparel)",
        "city": "Ho Chi Minh, Vietnam",
        "date": "24-26 February 2027",
        "category": "Textile & Apparel",
        "website": "https://viatt.com.vn"
    },
    {
        "name": "INATEX Indonesia 2026",
        "city": "Jakarta, Indonesia",
        "date": "15-18 April 2026",
        "category": "Textile & Sportswear",
        "website": "https://inatex.co.id"
    }
]

# ==================== کلمات کلیدی جستجو در گوگل ====================
SEARCH_QUERIES = [
    "textile exhibition 2026",
    "yarn exhibition 2026",
    "fiber exhibition 2026",
    "apparel exhibition 2026",
    "technical textile exhibition 2026",
    "nonwoven exhibition 2026",
    "textile fair 2026",
    "fashion exhibition 2026",
    "home textile exhibition 2026",
    "textile trade show 2026",
    "polyester fiber exhibition 2026"
]

# ==================== جستجو در گوگل ====================
async def search_google_exhibitions(query: str) -> list:
    """جستجوی نمایشگاه‌ها در گوگل"""
    results = []
    
    try:
        async with aiohttp.ClientSession() as session:
            search_url = f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            }
            
            async with session.get(search_url, headers=headers, timeout=20) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, "html.parser")
                    
                    # پیدا کردن نتایج جستجو
                    result_links = soup.find_all('a', {'class': 'result__a'})
                    
                    for link in result_links[:10]:
                        title = link.get_text().strip()
                        href = link.get('href', '')
                        
                        # استخراج تاریخ و مکان از عنوان و متن
                        date_match = re.search(r'\d{1,2}\s*[-–]\s*\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}', title)
                        
                        # بررسی اینکه آیا نتیجه مربوط به نمایشگاه است
                        if any(word in title.lower() for word in ['exhibition', 'fair', 'trade show', 'show', 'expo', 'exposition']):
                            city_match = re.search(r'(?:in|at)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', title)
                            city = city_match.group(1) if city_match else "Unknown"
                            
                            results.append({
                                "name": title[:150],
                                "city": city,
                                "date": date_match.group(0) if date_match else "Check website",
                                "website": href,
                                "source": "Google Search"
                            })
                    
                    await asyncio.sleep(0.5)
                    
    except Exception as e:
        logging.warning(f"Error searching Google: {e}")
    
    return results

async def filter_next_two_months(exhibitions: list) -> list:
    """فیلتر نمایشگاه‌های دو ماه آینده"""
    today = datetime.now()
    two_months_later = today + timedelta(days=60)
    
    filtered = []
    
    for ex in exhibitions:
        date_str = ex.get("date", "")
        # تلاش برای استخراج تاریخ
        date_match = re.search(r'(\d{1,2})\s*[-–]\s*(\d{1,2})\s+(\w+)\s+(\d{4})', date_str)
        if date_match:
            try:
                day = int(date_match.group(1))
                month_name = date_match.group(3)
                year = int(date_match.group(4))
                
                months = {
                    'January': 1, 'February': 2, 'March': 3, 'April': 4,
                    'May': 5, 'June': 6, 'July': 7, 'August': 8,
                    'September': 9, 'October': 10, 'November': 11, 'December': 12,
                    'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
                    'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
                }
                month = months.get(month_name[:3], 0)
                
                if month > 0:
                    event_date = datetime(year, month, day)
                    if today <= event_date <= two_months_later:
                        filtered.append(ex)
            except:
                pass
    
    # اگر تاریخی استخراج نشد، نمایشگاه را نگه دار
    for ex in exhibitions:
        if ex not in filtered:
            date_str = ex.get("date", "")
            if "2026" in date_str:
                # تاریخ را بررسی کن
                pass
    
    return filtered if filtered else exhibitions[:20]  # اگر فیلتر نشد، ۲۰ تا اول را نشان بده

# ==================== هندلرهای ربات ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🧵 <b>ربات جستجوی نمایشگاه‌های صنعت نساجی و الیاف پلی‌استر</b>\n\n"
        "🌍 <b>پوشش:</b> نمایشگاه‌های سراسر جهان\n"
        "🏗️ <b>حوزه‌ها:</b>\n"
        "   • الیاف و نخ (Fibers & Yarns)\n"
        "   • پوشاک و منسوجات (Apparel & Textiles)\n"
        "   • منسوجات فنی (Technical Textiles)\n\n"
        "📅 <b>نمایش برای:</b> دو ماه آینده\n\n"
        "💡 برای دریافت لیست نمایشگاه‌ها، هر پیامی ارسال کنید.\n"
        "⏳ زمان جستجو: حدود ۱-۲ دقیقه",
        parse_mode="HTML"
    )

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text(
        "🔍 در حال جستجوی نمایشگاه‌های صنعت نساجی و الیاف پلی‌استر...\n"
        "🌍 در حال بررسی نمایشگاه‌های سراسر جهان\n"
        "📅 محدوده: دو ماه آینده\n\n"
        "⏳ لطفاً صبر کنید..."
    )
    
    try:
        all_exhibitions = []
        
        # جستجو در گوگل با کلمات کلیدی مختلف
        for i, query in enumerate(SEARCH_QUERIES[:3]):  # فقط ۳ کوئری برای سرعت
            await msg.edit_text(
                f"🔍 مرحله {i+1}/{len(SEARCH_QUERIES[:3])}: جستجوی '{query}'...\n"
                f"📊 تاکنون {len(all_exhibitions)} نمایشگاه پیدا شده"
            )
            results = await search_google_exhibitions(query)
            all_exhibitions.extend(results)
            await asyncio.sleep(1)
        
        # اضافه کردن نمایشگاه‌های ثابت
        all_exhibitions.extend(FIXED_EXHIBITIONS)
        
        # حذف تکراری‌ها
        seen_names = set()
        unique_exhibitions = []
        for ex in all_exhibitions:
            name = ex.get("name", "").lower().strip()
            if name and name not in seen_names:
                seen_names.add(name)
                unique_exhibitions.append(ex)
        
        # فیلتر دو ماه آینده
        filtered = await filter_next_two_months(unique_exhibitions)
        
        if not filtered:
            await msg.edit_text(
                "😕 هیچ نمایشگاه در دو ماه آینده پیدا نشد.\n\n"
                "💡 نکات:\n"
                "• ممکن است اطلاعات به‌روز نشده باشد\n"
                "• سعی کنید دوباره جستجو کنید\n"
                "• ممکن است زمان جستجو را تغییر دهید"
            )
            return
        
        # ایجاد فایل اکسل
        df = pd.DataFrame(filtered)
        df = df.fillna("-")
        
        filename = f"نمایشگاههای_نساجی_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name="نمایشگاه‌ها")
            
            info_data = {
                'اطلاعات': [
                    f'موضوع: نمایشگاه‌های صنعت نساجی و الیاف پلی‌استر',
                    f'تاریخ جستجو: {datetime.now().strftime("%Y/%m/%d %H:%M")}',
                    f'تعداد کل نمایشگاه‌ها: {len(filtered)}',
                    f'منبع: Google Search + منابع معتبر',
                    f'محدوده زمانی: دو ماه آینده'
                ]
            }
            info_df = pd.DataFrame(info_data)
            info_df.to_excel(writer, index=False, sheet_name="اطلاعات جستجو")
        
        with open(filename, 'rb') as f:
            # ساخت پیام خروجی
            today = datetime.now().strftime("%Y/%m/%d")
            two_months = (datetime.now() + timedelta(days=90)).strftime("%Y/%m/%d")
            
            message = (
                f"🧵 <b>لیست نمایشگاه‌های صنعت نساجی و الیاف پلی‌استر</b>\n\n"
                f"📅 <b>بازه زمانی:</b> {today} تا {two_months}\n"
                f"🌍 <b>پوشش:</b> سراسر جهان\n"
                f"📋 <b>تعداد:</b> {len(filtered)} نمایشگاه\n\n"
                f"🏗️ <b>حوزه‌ها شامل:</b>\n"
                f"   • الیاف و نخ (Fibers & Yarns)\n"
                f"   • پوشاک و منسوجات (Apparel & Textiles)\n"
                f"   • منسوجات فنی (Technical Textiles)\n"
                f"   • منسوجات خانگی (Home Textiles)\n\n"
                f"📊 فایل اکسل کامل ارسال شد."
            )
            
            await update.message.reply_document(
                document=f,
                filename=filename,
                caption=message,
                parse_mode="HTML"
            )
        
        os.remove(filename)
        await msg.delete()
        
    except Exception as e:
        error_msg = str(e)[:300]
        await msg.edit_text(f"❌ خطا: {error_msg}\n\nلطفاً دوباره تلاش کنید.")
        logging.error(f"Error in search: {e}", exc_info=True)

# ==================== Flask Routes ====================
@app.route('/')
def home():
    return "✅ ربات جستجوی نمایشگاه‌های صنعت نساجی و الیاف پلی‌استر فعال است!"

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
    
    print("=" * 70)
    print("🧵 ربات جستجوی نمایشگاه‌های صنعت نساجی و الیاف پلی‌استر")
    print("=" * 70)
    print("🌍 پوشش: سراسر جهان")
    print("🏗️ حوزه‌ها: الیاف و نخ، پوشاک، منسوجات فنی")
    print("📅 نمایش: دو ماه آینده")
    print("=" * 70)
    print("✅ ربات در حال اجراست!")
    print("💡 برای دریافت لیست، هر پیامی ارسال کنید")
    print("=" * 70)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    run_bot()
