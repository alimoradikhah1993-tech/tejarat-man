import asyncio
from telegram import Bot

TOKEN = "YOUR_BOT_TOKEN"
CHAT_ID = "YOUR_CHAT_ID"

bot = Bot(token=TOKEN)


async def _send(text):
    await bot.send_message(chat_id=CHAT_ID, text=text)


def send_report(text):
    try:
        asyncio.run(_send(text))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_send(text))
