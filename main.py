import os
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# گرفتن توکن‌ها از Render
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")


def search_companies(query):
    q = f"{query} Russia concrete company factory"

    url = "https://serpapi.com/search.json"
    params = {
        "q": q,
        "engine": "google",
        "api_key": SERPAPI_KEY,
        "gl": "ru",
        "hl": "en"
    }

    data = requests.get(url, params=params).json()

    results = []

    for item in data.get("organic_results", [])[:7]:
        title = item.get("title", "")
        results.append(f"🏢 {title}")

    return "\n".join(results)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام 👋\nکلمه رو بفرست (مثلاً: روان کننده بتن)")


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text

    await update.message.reply_text("🔍 در حال جستجو...")

    result = search_companies(query)

    await update.message.reply_text(result if result else "چیزی پیدا نشد")


app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

app.run_polling()
