import os
import asyncio
import re
import pandas as pd
from datetime import datetime
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import logging
import threading
import aiohttp
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)

TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN is not set!")

app = Flask(__name__)

# ==================== بقیه کدها (همان کد قبلی) ====================
# ... (کدهای توابع search_vk, search_linkedin, start, search) ...

# ==================== Flask Routes ====================
@app.route('/')
def home():
    return "✅ ربات جستجوی شرکت‌های واردکننده فعال است!"

@app.route('/health')
def health():
    return "OK", 200

# ==================== اجرا ====================
def run_flask():
    """اجرای Flask در یک ترد جداگانه برای باز کردن پورت"""
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def run_bot():
    """راه‌اندازی ربات"""
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))
    
    print("=" * 60)
    print("🤖 ربات جستجوی شرکت‌های واردکننده و توزیع‌کننده")
    print("=" * 60)
    print("✅ ربات در حال اجراست!")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    # اجرای Flask در ترد جداگانه
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # اجرای ربات در ترد اصلی
    run_bot()
