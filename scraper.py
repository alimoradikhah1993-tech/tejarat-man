import aiohttp
import asyncio
from bs4 import BeautifulSoup
import logging
import re

logging.basicConfig(level=logging.INFO)

# دیکشنری ترجمه کلمات کلیدی (قابل گسترش است)
TRANSLATION_DICT = {
    # فارسی به روسی
    "بتن": "бетон",
    "افزودنی": "добавки",
    "سیمان": "цемент",
    "گچ": "гипс",
    "چسب": "клей",
    "رزین": "смола",
    "عایق": "изоляция",
    "رنگ": "краска",
    "شیمی": "химия",
    "ساختمان": "строительство",
    "مصالح": "материалы",
    "پلاستیک": "пластик",
    "فوم": "пена",
    "چوب": "дерево",
    "فلز": "металл",
    # انگلیسی به روسی (برای کسانی که انگلیسی تایپ می‌کنند)
    "concrete": "бетон",
    "additive": "добавки",
    "cement": "цемент",
    "glue": "клей",
    "resin": "смола",
    "paint": "краска",
    "chemical": "химия",
    "construction": "строительство",
    "materials": "материалы",
}

def translate_to_russian(text: str) -> str:
    """
    تبدیل کلمه فارسی/انگلیسی به روسی
    اگر کلمه در دیکشنری نباشد، همان را برمی‌گرداند
    """
    text_lower = text.lower().strip()
    
    # چک کردن تطابق کامل
    if text_lower in TRANSLATION_DICT:
        return TRANSLATION_DICT[text_lower]
    
    # چک کردن کلمات ترکیبی (مثلاً "افزودنی بتن")
    words = text_lower.split()
    translated_words = []
    for word in words:
        if word in TRANSLATION_DICT:
            translated_words.append(TRANSLATION_DICT[word])
        else:
            translated_words.append(word)
    
    return " ".join(translated_words)

async def search_msp(keyword: str) -> list:
    """
    جستجوی شرکت‌های روسی برای هر کالایی
    """
    found_companies = []
    
    # 1. ترجمه کلمه به روسی
    russian_keyword = translate_to_russian(keyword)
    logging.info(f"کلمه اصلی: {keyword} → ترجمه به روسی: {russian_keyword}")
    
    # 2. اگر کلمه ترجمه نشد، از خود کلمه استفاده کن
    if russian_keyword == keyword:
        # شاید کاربر خودش روسی تایپ کرده
        russian_keyword = keyword
    
    # 3. جستجو در متاپروم با کلمه روسی
    search_url = f"https://metaprom.ru/search/?q={russian_keyword}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        await asyncio.sleep(1)  # تأخیر برای جلوگیری از بلاک شدن
        async with aiohttp.ClientSession() as session:
            async with session.get(search_url, headers=headers, timeout=20) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, "html.parser")
                    
                    # جستجو برای نام شرکت‌ها
                    for item in soup.select(".catalog-item__title, .company-item__title"):
                        name = item.get_text(strip=True)
                        if name and len(name) > 3 and name not in str(found_companies):
                            found_companies.append(f"{name} (Metaprom)")
                else:
                    logging.warning(f"خطا در متاپروم: {response.status}")
                    
    except Exception as e:
        logging.error(f"خطا در اتصال به متاپروم: {e}")
        found_companies.append(f"⚠️ خطا در اتصال به Metaprom: {str(e)[:100]}")
    
    # 4. اگر نتیجه‌ای پیدا نشد، پیام مناسب برگردان
    if not found_companies:
        found_companies.append(f"هیچ شرکتی برای «{keyword}» پیدا نشد.")
        found_companies.append(f"کلمه جستجو شده به روسی: {russian_keyword}")
        found_companies.append("سعی کنید با کلمات کلیدی دیگری جستجو کنید.")
    
    return found_companies[:15]
