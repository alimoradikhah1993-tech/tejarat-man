import aiohttp
import asyncio
from bs4 import BeautifulSoup

async def search_msp(keyword: str) -> list:
    """
    جستجوی شرکت‌ها در پلتفرم MSP.RU با کلمه کلیدی
    برمی‌گرداند: لیست نام شرکت‌ها
    """
    # تبدیل کلمه به حروف روسی (اگر فارسی یا انگلیسی بود)
    # برای سادگی فعلاً همان کلمه را می‌فرستیم
    search_url = f"https://мсп.рф/search?q={keyword}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    companies = []
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(search_url, headers=headers, timeout=30) as response:
                if response.status != 200:
                    return [f"خطا: وضعیت {response.status}"]
                
                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")
                
                # پیدا کردن نام شرکت‌ها (این سلکتورها نمونه‌ست؛ باید دقیق شود)
                # معمولاً در سایت MSP.RU شرکت‌ها در تگ‌های h3 یا div با کلاس خاصی هستند
                for item in soup.select(".company-name, .org-name, .title"):
                    name = item.get_text(strip=True)
                    if name and len(name) > 2:
                        companies.append(name)
                
                # اگر چیزی پیدا نشد، یک پیام آزمایشی برمی‌گردانیم
                if not companies:
                    companies = [
                        f"نمونه شرکت ۱ (برای {keyword})",
                        f"نمونه شرکت ۲ (برای {keyword})",
                        "این داده‌های آزمایشی است. سلکتورها باید دقیق شوند."
                    ]
                    
    except Exception as e:
        companies = [f"خطا در اتصال: {str(e)}"]
    
    return companies[:30]  # حداکثر ۳۰ نتیجه
