import os
import asyncio
from telegram import Bot

TOKEN = os.environ.get("TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

bot = Bot(token=TOKEN)

async def _send(text):
    await bot.send_message(chat_id=CHAT_ID, text=text)

def send_report(text):
    asyncio.run(_send(text))
