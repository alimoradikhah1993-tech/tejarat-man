from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler

from news import get_trade_news
from analyzer import analyze_news
from bot import send_report
send_report("🟢 تست موفق: ربات به تلگرام وصل شد")
app = Flask(__name__)

def job():
    news = get_trade_news()
    insights, opportunities = analyze_news(news)

    message = "📊 تحلیل تجارت روسیه و آذربایجان\n\n"

    message += "🧠 اخبار مهم:\n"
    message += "\n".join(insights[:10])

    message += "\n\n🇮🇷 فرصت‌های صادرات ایران:\n"
    message += "\n".join(opportunities[:10])

    send_report(message)

scheduler = BackgroundScheduler()
scheduler.add_job(job, 'interval', minutes=15)
scheduler.start()

@app.route("/")
def home():
    return "Bot is running"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
    send_report("🟢 تست ربات موفق بود")
