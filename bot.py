from telegram import Bot

TOKEN = "YOUR_BOT_TOKEN"
CHAT_ID = "YOUR_CHAT_ID"

bot = Bot(token=TOKEN)

def send_report(text):
    bot.send_message(chat_id=CHAT_ID, text=text)
