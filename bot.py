from telegram import Bot
import asyncio

TOKEN = "YOUR_BOT_TOKEN"
CHAT_ID = "YOUR_CHAT_ID"

bot = Bot(token=TOKEN)


async def _send(text):
    await bot.send_message(chat_id=CHAT_ID, text=text)


def send_report(text):
    try:
        asyncio.run(_send(text))
    except RuntimeError:
        # وقتی event loop بازه (Render / scheduler)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_send(text))import os
from telegram import Bot

TOKEN = os.environ.get("TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

bot = Bot(token=TOKEN)

def send_report(text):
    bot.send_message(chat_id=CHAT_ID, text=text)
