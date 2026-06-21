import os
import asyncio
import pandas as pd
from datetime import datetime
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import logging
import threading

logging.basicConfig(level=logging.INFO)

TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set!")

app = Flask(__name__)

# ==================== لیست کامل نمایشگاه‌ها تا پایان 2026 ====================
EXHIBITIONS = {
    "🇹🇷 ترکیه": [
        {"name": "ICFE - International Carpet & Flooring Expo", "city": "استانبول", "date": "۶-۹ ژانویه ۲۰۲۶", "category": "فرش، الیاف، نخ"},
        {"name": "Junioshow", "city": "بورسا", "date": "۲۰-۲۲ ژانویه ۲۰۲۶", "category": "پوشاک کودک و نوزاد"},
        {"name": "IF Wedding Fashion Izmir", "city": "ازمیر", "date": "۲۰-۲۲ ژانویه ۲۰۲۶", "category": "پوشاک عروس و مجالس"},
        {"name": "Istanbul Fashion Connection (IFCO) - Winter", "city": "استانبول", "date": "۴-۷ فوریه ۲۰۲۶", "category": "پوشاک زنانه، مردانه، بچگانه، جین"},
        {"name": "Texhibition Istanbul", "city": "استانبول", "date": "مارس ۲۰۲۶", "category": "پارچه، جین، منسوجات پایدار"},
        {"name": "HOMETEX", "city": "استانبول", "date": "می ۲۰۲۶", "category": "منسوجات خانگی"},
        {"name": "ITM 2026", "city": "استانبول", "date": "۹-۱۳ ژوئن ۲۰۲۶", "category": "ماشین‌آلات نساجی و فناوری"},
        {"name": "Hightex 2026", "city": "استانبول", "date": "۹-۱۳ ژوئن ۲۰۲۶", "category": "منسوجات فنی و نبافته"},
        {"name": "Istanbul Fashion Connection (IFCO) - Summer", "city": "استانبول", "date": "۱۹-۲۱ اوت ۲۰۲۶", "category": "پوشاک و مد"},
    ],
    "🇨🇳 چین": [
        {"name": "Yarn Expo Spring 2026", "city": "شانگهای", "date": "۱۱-۱۳ مارس ۲۰۲۶", "category": "الیاف و نخ"},
        {"name": "Intertextile Shanghai Apparel Fabrics (Spring)", "city": "شانگهای", "date": "۱۱-۱۳ مارس ۲۰۲۶", "category": "پارچه‌های پوشاک"},
        {"name": "Intertextile Shanghai Home Textiles", "city": "شانگهای", "date": "۱۸-۲۰ اوت ۲۰۲۶", "category": "منسوجات خانگی"},
        {"name": "CINTE Techtextil China", "city": "شانگهای", "date": "۱-۳ سپتامبر ۲۰۲۶", "category": "منسوجات فنی و نبافته"},
        {"name": "ITMA Asia + CITME", "city": "شانگهای", "date": "۲۰-۲۴ نوامبر ۲۰۲۶", "category": "ماشین‌آلات نساجی"},
    ],
    "🇫🇷 فرانسه": [
        {"name": "Texworld Apparel Sourcing Paris", "city": "پاریس", "date": "۲-۴ فوریه ۲۰۲۶", "category": "تأمین‌کنندگان پوشاک"},
        {"name": "Première Vision Paris", "city": "پاریس", "date": "۳-۵ فوریه ۲۰۲۶", "category": "پارچه‌های لوکس و طراحی"},
        {"name": "Texworld Apparel Sourcing Paris (Autumn)", "city": "پاریس", "date": "سپتامبر ۲۰۲۶", "category": "تأمین‌کنندگان پوشاک"},
    ],
    "🇺🇸 آمریکا": [
        {"name": "MAGIC Las Vegas", "city": "لاس‌وگاس", "date": "۱۷-۱۹ فوریه ۲۰۲۶", "category": "مد، پوشاک، کفش، اکسسوری"},
        {"name": "Texworld New York City", "city": "نیویورک", "date": "تابستان و زمستان ۲۰۲۶", "category": "پارچه و منسوجات"},
        {"name": "World of Wipes", "city": "نشویل، تنسی", "date": "۲۹ ژوئن - ۲ ژوئیه ۲۰۲۶", "category": "منسوجات بهداشتی و نبافته"},
        {"name": "Functional Fabric Fair", "city": "نامشخص", "date": "۷-۹ ژوئیه ۲۰۲۶", "category": "منسوجات فنی، ورزشی"},
        {"name": "Home Textiles Sourcing Los Angeles", "city": "لس‌آنجلس", "date": "۲۱-۲۳ ژوئیه ۲۰۲۶", "category": "منسوجات خانگی"},
        {"name": "Texworld Los Angeles", "city": "لس‌آنجلس", "date": "۲۱-۲۳ ژوئیه ۲۰۲۶", "category": "پارچه و منسوجات"},
        {"name": "Apparel Sourcing Los Angeles", "city": "لس‌آنجلس", "date": "۲۱-۲۳ ژوئیه ۲۰۲۶", "category": "پوشاک"},
        {"name": "Home Textiles Sourcing New York", "city": "نیویورک", "date": "۲۹-۳۱ ژوئیه ۲۰۲۶", "category": "منسوجات خانگی"},
        {"name": "Techtextil North America", "city": "رالی، کارولینای شمالی", "date": "۴-۶ اوت ۲۰۲۶", "category": "منسوجات فنی و نبافته"},
        {"name": "Advanced Textiles Expo", "city": "اورلاندو، فلوریدا", "date": "۳-۵ نوامبر ۲۰۲۶", "category": "منسوجات پیشرفته"},
    ],
    "🇩🇪 آلمان": [
        {"name": "Techtextil", "city": "فرانکفورت", "date": "۲۱-۲۴ آوریل ۲۰۲۶", "category": "منسوجات فنی و نبافته"},
        {"name": "Munich Fabric Start", "city": "مونیخ", "date": "۱۴-۱۶ ژوئیه ۲۰۲۶", "category": "پارچه و جین"},
        {"name": "Filtech", "city": "کلن", "date": "۳۰ ژوئن - ۲ ژوئیه ۲۰۲۶", "category": "فناوری فیلتراسیون"},
        {"name": "Heimtextil 2027", "city": "فرانکفورت", "date": "۱۲-۱۵ ژانویه ۲۰۲۷", "category": "منسوجات خانگی"},
    ],
    "🇮🇳 هند": [
        {"name": "India International Garment Fair (IIGF)", "city": "دهلی نو", "date": "۲۳-۲۵ ژانویه ۲۰۲۶", "category": "پوشاک"},
        {"name": "Bharat Tex 2026", "city": "دهلی نو", "date": "۱۴-۱۷ ژوئیه ۲۰۲۶", "category": "زنجیره کامل ارزش نساجی"},
    ],
    "🇮🇹 ایتالیا": [
        {"name": "Milano Unica", "city": "میلان", "date": "فوریه و ژوئیه ۲۰۲۶", "category": "پارچه‌های لوکس"},
    ],
    "🇦🇪 امارات": [
        {"name": "IATF - International Apparel & Textile Fair", "city": "دبی", "date": "۲۳-۲۵ ژوئن ۲۰۲۶", "category": "مد و نساجی"},
    ],
    "🇦🇹 اتریش": [
        {"name": "Dornbirn Global Fiber Congress", "city": "دورنبیرن", "date": "۱۶-۱۸ سپتامبر ۲۰۲۶", "category": "الیاف پیشرفته و نوآوری"},
    ],
    "🇨🇦 کانادا": [
        {"name": "Apparel Textile Sourcing", "city": "تورنتو", "date": "۲۳-۲۵ سپتامبر ۲۰۲۶", "category": "پوشاک و منسوجات"},
    ],
    "🇧🇪 بلژیک": [
        {"name": "Textiles Recycling Expo", "city": "بروکسل", "date": "۲۴-۲۵ ژوئن ۲۰۲۶", "category": "بازیافت منسوجات"},
    ],
    "🇲🇽 مکزیک": [
        {"name": "FESPA Mexico", "city": "مکزیکو سیتی", "date": "۱۰-۱۲ سپتامبر ۲۰۲۶", "category": "چاپ و تکمیل منسوجات"},
    ],
    "🇶🇦 قطر": [
        {"name": "Milipol Qatar", "city": "دوحه", "date": "۲۰-۲۲ اکتبر ۲۰۲۶", "category": "منسوجات حفاظتی و امنیتی"},
    ],
    "🇬🇧 بریتانیا": [
        {"name": "Advanced Engineering", "city": "بیرمنگام", "date": "۴-۵ نوامبر ۲۰۲۶", "category": "منسوجات فنی و مهندسی"},
    ],
    "🇪🇸 اسپانیا": [
        {"name": "Outlook", "city": "کاسکایس، پرتغال", "date": "۲۲-۲۴ سپتامبر ۲۰۲۶", "category": "منسوجات نبافته"},
    ],
}

# ==================== هندلرهای ربات ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🧵 <b>ربات نمایشگاه‌های صنعت نساجی و الیاف پلی‌استر</b>\n\n"
        "🌍 <b>پوشش:</b> نمایشگاه‌های سراسر جهان تا پایان ۲۰۲۶\n"
        "🏗️ <b>حوزه‌ها شامل:</b>\n"
        "   • الیاف و نخ (Fibers & Yarns)\n"
        "   • پوشاک و منسوجات (Apparel & Textiles)\n"
        "   • منسوجات فنی (Technical Textiles)\n"
        "   • منسوجات خانگی (Home Textiles)\n"
        "   • ماشین‌آلات نساجی\n\n"
        f"📊 <b>تعداد کل نمایشگاه‌ها:</b> {sum(len(ex) for ex in EXHIBITIONS.values())}\n"
        f"🌍 <b>تعداد کشورها:</b> {len(EXHIBITIONS)}\n\n"
        "💡 برای دریافت لیست کامل، هر پیامی ارسال کنید.",
        parse_mode="HTML"
    )

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text(
        "🧵 در حال آماده‌سازی لیست نمایشگاه‌ها...\n"
        f"📊 {sum(len(ex) for ex in EXHIBITIONS.values())} نمایشگاه در {len(EXHIBITIONS)} کشور\n"
        "⏳ لطفاً صبر کنید..."
    )
    
    try:
        # ساخت پیام خروجی
        total = sum(len(ex) for ex in EXHIBITIONS.values())
        message = f"🧵 <b>لیست کامل نمایشگاه‌های صنعت نساجی و الیاف پلی‌استر</b>\n"
        message += f"📅 <b>تا پایان سال ۲۰۲۶</b>\n"
        message += f"🌍 <b>تعداد کشورها:</b> {len(EXHIBITIONS)}\n"
        message += f"📋 <b>تعداد کل نمایشگاه‌ها:</b> {total}\n"
        message += "─" * 40 + "\n\n"
        
        # اضافه کردن هر کشور به تفکیک
        for country, exhibitions in EXHIBITIONS.items():
            message += f"<b>{country}</b> ({len(exhibitions)} نمایشگاه)\n"
            message += "─" * 30 + "\n"
            
            for i, ex in enumerate(exhibitions, 1):
                message += f"  {i}. <b>{ex['name']}</b>\n"
                message += f"     📍 {ex['city']}\n"
                message += f"     📅 {ex['date']}\n"
                message += f"     🏷️ {ex['category']}\n\n"
            
            message += "\n"
        
        # اگر پیام خیلی طولانی شد، به دو بخش تقسیم کن
        if len(message) > 4096:
            # بخش اول: اطلاعات کلی
            first_part = f"🧵 <b>لیست کامل نمایشگاه‌ها تا پایان ۲۰۲۶</b>\n"
            first_part += f"🌍 {len(EXHIBITIONS)} کشور\n"
            first_part += f"📋 {total} نمایشگاه\n\n"
            first_part += "⚠️ لیست کامل در فایل اکسل ارسال شد."
            
            # ایجاد فایل اکسل
            all_data = []
            for country, exhibitions in EXHIBITIONS.items():
                for ex in exhibitions:
                    all_data.append({
                        "کشور": country.replace("🇹🇷", "").replace("🇨🇳", "").replace("🇫🇷", "").replace("🇺🇸", "").replace("🇩🇪", "").replace("🇮🇳", "").replace("🇮🇹", "").replace("🇦🇪", "").replace("🇦🇹", "").replace("🇨🇦", "").replace("🇧🇪", "").replace("🇲🇽", "").replace("🇶🇦", "").replace("🇬🇧", "").replace("🇪🇸", "").strip(),
                        "نام نمایشگاه": ex['name'],
                        "شهر": ex['city'],
                        "تاریخ": ex['date'],
                        "حوزه تخصصی": ex['category']
                    })
            
            df = pd.DataFrame(all_data)
            filename = f"نمایشگاههای_نساجی_کامل_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
            df.to_excel(filename, index=False)
            
            with open(filename, 'rb') as f:
                await update.message.reply_document(
                    document=f,
                    filename=filename,
                    caption=f"🧵 <b>لیست کامل نمایشگاه‌های نساجی تا پایان ۲۰۲۶</b>\n\n"
                           f"🌍 {len(EXHIBITIONS)} کشور\n"
                           f"📋 {total} نمایشگاه\n"
                           f"📅 تاریخ: {datetime.now().strftime('%Y/%m/%d %H:%M')}",
                    parse_mode="HTML"
                )
            
            os.remove(filename)
            await msg.delete()
            return
        
        # ارسال پیام
        await msg.edit_text(message, parse_mode="HTML")
        
        # ارسال فایل اکسل نیز
        all_data = []
        for country, exhibitions in EXHIBITIONS.items():
            for ex in exhibitions:
                all_data.append({
                    "کشور": country.replace("🇹🇷", "").replace("🇨🇳", "").replace("🇫🇷", "").replace("🇺🇸", "").replace("🇩🇪", "").replace("🇮🇳", "").replace("🇮🇹", "").replace("🇦🇪", "").replace("🇦🇹", "").replace("🇨🇦", "").replace("🇧🇪", "").replace("🇲🇽", "").replace("🇶🇦", "").replace("🇬🇧", "").replace("🇪🇸", "").strip(),
                    "نام نمایشگاه": ex['name'],
                    "شهر": ex['city'],
                    "تاریخ": ex['date'],
                    "حوزه تخصصی": ex['category']
                })
        
        df = pd.DataFrame(all_data)
        filename = f"نمایشگاههای_نساجی_کامل_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        df.to_excel(filename, index=False)
        
        with open(filename, 'rb') as f:
            await update.message.reply_document(
                document=f,
                filename=filename,
                caption=f"📊 <b>فایل اکسل نمایشگاه‌ها</b>\n\n"
                       f"📋 {total} نمایشگاه\n"
                       f"🌍 {len(EXHIBITIONS)} کشور",
                parse_mode="HTML"
            )
        
        os.remove(filename)
        
    except Exception as e:
        await msg.edit_text(f"❌ خطا: {str(e)[:200]}\n\nلطفاً دوباره تلاش کنید.")
        logging.error(f"Error: {e}")

# ==================== Flask ====================
@app.route('/')
def home():
    return "✅ ربات نمایشگاه‌های صنعت نساجی و الیاف پلی‌استر فعال است!"

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
    
    total = sum(len(ex) for ex in EXHIBITIONS.values())
    print("=" * 70)
    print("🧵 ربات نمایشگاه‌های صنعت نساجی و الیاف پلی‌استر")
    print("=" * 70)
    print(f"🌍 {len(EXHIBITIONS)} کشور")
    print(f"📋 {total} نمایشگاه تا پایان 2026")
    print("=" * 70)
    print("✅ ربات در حال اجراست!")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    run_bot()
