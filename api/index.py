import os
import aiohttp
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import Update

# --- НАСТРОЙКИ ---
# Токен берется из Environment Variables в Vercel
TOKEN = os.getenv("BOT_TOKEN")

# Инициализация
app = FastAPI()
bot = Bot(TOKEN)
dp = Dispatcher()

# --- ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ (COBALT API) ---
async def get_download_url(url: str):
    """
    Отправляет ссылку на Cobalt API и получает прямую ссылку на видео-файл.
    """
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    body = {
        "url": url,
        "vCodec": "h264" # Кодек, который понимает Телеграм
    }
    
    # Публичный инстанс Cobalt. Если перестанет работать, нужно найти другой
    # Список инстансов: https://instances.hyper.lol/
    api_url = "https://co.wuk.sh/api/json" 
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(api_url, json=body, headers=headers) as response:
                if response.status != 200:
                    return None
                data = await response.json()
                
                # Cobalt может вернуть разные статусы
                if data.get('status') == 'stream':
                    return data.get('url')
                elif data.get('status') == 'redirect':
                    return data.get('url')
                elif data.get('status') == 'picker': # Если видео состоит из нескольких частей (редко)
                    return data.get('picker')[0].get('url')
                else:
                    return None
        except Exception as e:
            print(f"API Error: {e}")
            return None

# --- ХЕНДЛЕРЫ БОТА ---

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    await message.answer(
        "Привет! 👋\n"
        "Я умею скачивать видео из TikTok, Instagram (Reels) и YouTube.\n"
        "Просто пришли мне ссылку!"
    )

@dp.message()
async def download_handler(message: types.Message):
    text = message.text
    
    # Простейшая проверка на ссылку
    if not text or "http" not in text:
        await message.answer("Это не похоже на ссылку. Пришли мне URL видео.")
        return

    # Отправляем сообщение "Ожидайте..."
    status_msg = await message.answer("🔎 Ищу видео, подожди секунду...")
    
    try:
        # 1. Получаем прямую ссылку через API
        direct_url = await get_download_url(text)
        
        if direct_url:
            # 2. Отправляем видео в Телеграм ПО ССЫЛКЕ
            # (Телеграм сам скачивает его к себе на сервера и показывает пользователю)
            await message.answer_video(
                video=direct_url,
                caption="Готово! 📹",
                reply_to_message_id=message.message_id
            )
            await status_msg.delete()
        else:
            await status_msg.edit_text("😔 Не удалось получить видео. Возможно, ссылка закрытая или сервис перегружен.")
            
    except Exception as e:
        # Если ссылка битая или файл слишком большой для загрузки по URL
        await status_msg.edit_text(f"Произошла ошибка при отправке: {e}")

# --- WEBHOOK ЛОГИКА (ДЛЯ VERCEL) ---

@app.post("/webhook")
async def webhook_handler(request: Request):
    try:
        update_data = await request.json()
        update = Update.model_validate(update_data, context={"bot": bot})
        await dp.feed_update(bot, update)
        return {"status": "ok"}
    except Exception as e:
        print(f"Error handling update: {e}")
        return {"status": "error"}

@app.get("/")
async def index():
    return {"message": "Bot is active! Don't forget to set webhook."}