import os
import aiohttp
import asyncio
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import Update

# --- НАСТРОЙКИ ---
TOKEN = os.getenv("BOT_TOKEN")

app = FastAPI()
bot = Bot(TOKEN)
dp = Dispatcher()

# --- СПИСОК СЕРВЕРОВ ---
# Мы будем пробовать их по очереди.
# Список взят из https://instances.hyper.lol/
COBALT_INSTANCES = [
    "https://api.cobalt.tools/api/json",      # Официальный (часто перегружен)
    "https://co.wuk.sh/api/json",             # Популярный
    "https://cobalt.xyzen.dev/api/json",      # Альтернатива 1
    "https://api.server.social/api/json",     # Альтернатива 2
    "https://cobalt.razex.app/api/json",      # Альтернатива 3
]

# --- НОВАЯ ФУНКЦИЯ (С ПЕРЕБОРОМ СЕРВЕРОВ) ---
async def get_download_url(url: str):
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    body = {
        "url": url,
        "vCodec": "h264"
    }

    async with aiohttp.ClientSession() as session:
        # Пробуем каждый сервер из списка
        for api_url in COBALT_INSTANCES:
            try:
                print(f"Пробую сервер: {api_url}") # Пишем в логи Vercel
                # Ставим таймаут 4 секунды, чтобы не висеть долго на одном сервере
                async with session.post(api_url, json=body, headers=headers, timeout=4) as response:
                    
                    if response.status != 200:
                        print(f"Сервер {api_url} вернул ошибку: {response.status}")
                        continue # Идем к следующему серверу

                    data = await response.json()
                    
                    # Логика обработки ответа Cobalt
                    direct_link = None
                    if data.get('status') == 'stream':
                        direct_link = data.get('url')
                    elif data.get('status') == 'redirect':
                        direct_link = data.get('url')
                    elif data.get('status') == 'picker':
                        # Берем первое доступное видео
                        direct_link = data.get('picker')[0].get('url')

                    if direct_link:
                        return direct_link # Успех! Возвращаем ссылку
            
            except Exception as e:
                print(f"Ошибка соединения с {api_url}: {e}")
                continue # Идем к следующему серверу
                
    return None # Если перебрали все и ничего не вышло

# --- ХЕНДЛЕРЫ ---

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    await message.answer("Привет! Пришли мне ссылку на TikTok, Reels или YouTube.")

@dp.message()
async def download_handler(message: types.Message):
    text = message.text
    
    if not text or "http" not in text:
        await message.answer("Это не ссылка.")
        return

    status_msg = await message.answer("🔎 Ищу рабочий сервер и качаю видео...")
    
    try:
        direct_url = await get_download_url(text)
        
        if direct_url:
            await message.answer_video(
                video=direct_url,
                caption="Готово! 📹",
                reply_to_message_id=message.message_id
            )
            await status_msg.delete()
        else:
            await status_msg.edit_text("😔 Все публичные серверы сейчас перегружены. Попробуй через минуту.")
            
    except Exception as e:
        await status_msg.edit_text(f"Ошибка Телеграм при отправке (возможно файл слишком большой): {e}")

# --- WEBHOOK ---

@app.post("/webhook")
async def webhook_handler(request: Request):
    try:
        update_data = await request.json()
        update = Update.model_validate(update_data, context={"bot": bot})
        await dp.feed_update(bot, update)
        return {"status": "ok"}
    except Exception as e:
        pass
    return {"status": "error"}

@app.get("/")
async def index():
    return {"message": "Bot is running"}