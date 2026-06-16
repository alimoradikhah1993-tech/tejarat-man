import asyncio
from telegram import Bot

TOKEN = "YOUR_BOT_TOKEN"
CHAT_ID = "YOUR_CHAT_ID"


async def _send(text):
    async with Bot(token=TOKEN) as bot:
        await bot.send_message(chat_id=CHAT_ID, text=text)


def send_report(text):
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_send(text))
    except RuntimeError:
        asyncio.run(_send(text))
