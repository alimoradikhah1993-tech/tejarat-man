import time
from flask import Flask

from news import get_trade_news
from analyzer import analyze_news
from bot import send_report

app = Flask(__name__)


def job():
    print("🔥 JOB STARTED")

    try:
        news = get_trade_news()
        print("📰 NEWS OK")

        insights, opportunities = analyze_news(news)
        print("🧠 ANALYSIS OK")

        message = "📊 تحلیل تجارت روسیه و آذربایجان\n\n"

        message += "🧠 تحلیل اخبار:\n"
        message += "\n".join(insights[:10])

        message += "\n\n🇮🇷 فرصت‌های صادرات ایران:\n"
        message += "\n".join(opportunities[:10])

        print("📨 SENDING MESSAGE")
        send_report(message)

        print("✅ DONE")

    except Exception as e:
        print("❌ ERROR:", str(e))
        send_report(f"🚨 ERROR:\n{str(e)}")


@app.route("/")
def home():
    return "AI Trade Bot is running"


if __name__ == "__main__":
    print("🚀 BOT STARTED")

    # 🔥 یک بار اول اجرا شود
    job()

    # 🔥 حلقه دائمی (هر 15 دقیقه)
    while True:
        time.sleep(900)  # 15 minutes
        job()

    app.run(host="0.0.0.0", port=10000)
