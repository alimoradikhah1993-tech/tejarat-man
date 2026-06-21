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

# ==================== حالت‌های کاربر ====================
WAITING_FOR_KEYWORD = {}

# ==================== جستجو در گوگل ====================
async def search_google_exhibitions(keyword: str) -> list:
    """جستجوی نمایشگاه‌ها در گوگل با کلمه کلیدی"""
    results = []
    
    try:
        async with aiohttp.ClientSession() as session:
            # ساخت عبارت جستجو
            search_query = f"{keyword} textile exhibition 2026 OR 2027 OR fair OR trade show"
            search_url = f"https://html.duckduckgo.com/html/?q={search_query.replace(' ', '+')}"
            
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
                    
                    for link in result_links[:30]:
                        title = link.get_text().strip()
                        href = link.get('href', '')
                        
                        # فقط نتایج مرتبط با نمایشگاه
                        if any(word in title.lower() for word in ['exhibition', 'fair', 'trade show', 'show', 'expo', 'exposition', 'event']):
                            # استخراج تاریخ
                            date_match = re.search(
                                r'(\d{1,2})\s*[-–]\s*(\d{1,2})\s+(\w+)\s+(\d{4})|'
                                r'(\d{1,2})\s+(\w+)\s+(\d{4})|'
                                r'(\w+)\s+(\d{4})',
                                title
                            )
                            
                            date = date_match.group(0) if date_match else "تاریخ نامشخص"
                            
                            # استخراج مکان
                            city_match = re.search(r'(?:in|at)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', title)
                            city = city_match.group(1) if city_match else "مکان نامشخص"
                            
                            results.append({
                                "name": title[:200],
                                "city": city,
                                "date": date,
                                "website": href,
                                "source": "Google Search"
                            })
                    
                    await asyncio.sleep(0.5)
                    
    except Exception as e:
        logging.warning(f"Error searching Google: {e}")
    
    return results

# ==================== هندلرهای ربات ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    WAITING_FOR_KEYWORD[user_id] = True
    
    await update.message.reply_text(
        "🧵 <b>ربات جستجوی نمایشگاه‌های صنعت نساجی و الیاف پلی‌استر</b>\n\n"
        "🌍 <b>پوشش:</b> نمایشگاه‌های سراسر جهان\n"
        "🏗️ <b>حوزه‌ها:</b>\n"
        "   • الیاف و نخ (Fibers & Yarns)\n"
        "   • پوشاک و منسوجات (Apparel & Textiles)\n"
        "   • منسوجات فنی (Technical Textiles)\n"
        "   • منسوجات خانگی (Home Textiles)\n\n"
        "🔍 <b>لطفاً کلمه کلیدی مورد نظر خود را وارد کنید:</b>\n\n"
        "📌 مثال‌ها:\n"
        "   • yarn exhibition\n"
        "   • textile fair\n"
        "   • polyester fiber show\n"
        "   • apparel trade show\n"
        "   • technical textile exhibition\n\n"
        "⏳ زمان جستجو: حدود ۱-۲ دقیقه",
        parse_mode="HTML"
    )

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    keyword = update.message.text.strip()
    
    # بررسی اینکه کاربر در حالت جستجو هست
    if user_id not in WAITING_FOR_KEYWORD or not WAITING_FOR_KEYWORD[user_id]:
        await update.message.reply_text(
            "❌ لطفاً ابتدا دستور /start را بزنید تا وارد حالت جستجو شوید."
        )
        return
    
    if len(keyword) < 3:
        await update.message.reply_text(
            "❌ کلمه کلیدی باید حداقل ۳ حرف باشد.\n"
            "مثال: yarn, textile, fiber, apparel"
        )
        return
    
    msg = await update.message.reply_text(
        f"🔍 در حال جستجوی نمایشگاه‌های مرتبط با: <b>«{keyword}»</b>\n"
        f"🌍 پوشش: سراسر جهان\n"
        f"⏳ لطفاً صبر کنید... (حدود ۱-۲ دقیقه)",
        parse_mode="HTML"
    )
    
    try:
        # جستجو در گوگل
        await msg.edit_text(
            f"🔍 مرحله ۱: جستجوی گوگل برای «{keyword}»...\n"
            f"⏳ در حال دریافت نتایج..."
        )
        
        results = await search_google_exhibitions(keyword)
        
        if not results:
            await msg.edit_text(
                f"😕 هیچ نمایشگاهی برای «{keyword}» پیدا نشد.\n\n"
                f"💡 نکات:\n"
                f"• از کلمات کلیدی عمومی‌تر استفاده کنید\n"
                f"• مثال: textile, yarn, fiber, apparel\n"
                f"• یا دوباره با /start شروع کنید"
            )
            WAITING_FOR_KEYWORD[user_id] = False
            return
        
        # حذف تکراری‌ها
        seen = set()
        unique_results = []
        for r in results:
            name = r['name'].lower().strip()
            if name not in seen:
                seen.add(name)
                unique_results.append(r)
        
        # ساخت پیام خروجی
        message = f"🧵 <b>نمایشگاه‌های مرتبط با «{keyword}»</b>\n"
        message += f"📅 تاریخ جستجو: {datetime.now().strftime('%Y/%m/%d %H:%M')}\n"
        message += f"📋 تعداد نتایج: {len(unique_results)}\n"
        message += "─" * 40 + "\n\n"
        
        for i, ex in enumerate(unique_results[:20], 1):  # حداکثر ۲۰ نتیجه
            message += f"{i}. <b>{ex['name'][:100]}</b>\n"
            message += f"   📍 {ex['city']}\n"
            message += f"   📅 {ex['date']}\n"
            if ex['website'] and ex['website'] != 'https:':
                message += f"   🔗 <a href='{ex['website']}'>لینک</a>\n"
            message += "\n"
        
        if len(unique_results) > 20:
            message += f"\n⚠️ <b>توجه:</b> {len(unique_results)} نتیجه پیدا شد، ۲۰ نتیجه اول نمایش داده شد."
        
        # ارسال پیام
        await msg.edit_text(message, parse_mode="HTML", disable_web_page_preview=True)
        
        # ایجاد فایل اکسل
        df = pd.DataFrame(unique_results)
        filename = f"نمایشگاههای_{keyword}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        df.to_excel(filename, index=False)
        
        with open(filename, 'rb') as f:
            await update.message.reply_document(
                document=f,
                filename=filename,
                caption=f"📊 <b>فایل اکسل نتایج جستجو</b>\n\n"
                       f"🔑 کلمه کلیدی: {keyword}\n"
                       f"📋 تعداد: {len(unique_results)} نمایشگاه\n"
                       f"📅 تاریخ: {datetime.now().strftime('%Y/%m/%d %H:%M')}",
                parse_mode="HTML"
            )
        
        os.remove(filename)
        
        # پایان حالت جستجو
        WAITING_FOR_KEYWORD[user_id] = False
        
        # پیشنهاد جستجوی جدید
        await update.message.reply_text(
            "✅ جستجو کامل شد!\n"
            "💡 برای جستجوی جدید، دوباره /start را بزنید."
        )
        
    except Exception as e:
        error_msg = str(e)[:300]
        await msg.edit_text(f"❌ خطا: {error_msg}\n\nلطفاً دوباره با /start شروع کنید.")
        logging.error(f"Error: {e}")
        WAITING_FOR_KEYWORD[user_id] = False

# ==================== Flask Routes ====================
@app.route('/')
def home():
    return "✅ ربات جستجوی نمایشگاه‌های صنعت نساجی فعال است!"

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
    print("🔍 روش: جستجوی گوگل (DuckDuckGo)")
    print("=" * 70)
    print("✅ ربات در حال اجراست!")
    print("💡 کاربران با /start شروع کرده و کلمه کلیدی را وارد می‌کنند")
    print("=" * 70)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    run_bot()
