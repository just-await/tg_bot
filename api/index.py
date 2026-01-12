import os
import random
import aiohttp
import asyncio
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import Update

TOKEN = os.getenv("BOT_TOKEN")
app = FastAPI()
bot = Bot(TOKEN)
dp = Dispatcher()

# Ссылка на мониторинг всех серверов Cobalt
INSTANCES_API = "https://instances.hyper.lol/api/instances.json"

async def get_working_instance():
    """
    Получает список живых серверов динамически.
    """
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(INSTANCES_API, timeout=5) as response:
                if response.status != 200:
                    return None
                
                data = await response.json()
                valid_instances = []
                
                for instance in data:
                    # Фильтруем серверы:
                    # 1. score == 1 (100% здоровье)
                    # 2. cors == 1 (разрешает запросы с чужих сайтов/ботов)
                    # 3. version >= 10 (поддерживает новый API)
                    # 4. Исключаем официальный, так как там капча (turnstile)
                    if (instance.get('score', 0) >= 0.9 and 
                        instance.get('cors', 0) == 1 and 
                        instance.get('version', '0').startswith('10') and
                        "cobalt.tools" not in instance.get('url', '')):
                        
                        # Убираем слеш в конце, если есть
                        url = instance.get('url').rstrip('/')
                        # Проверяем протокол
                        if url.startswith("https"):
                            valid_instances.append(url)
                
                if valid_instances:
                    # Берем случайный из рабочих, чтобы распределять нагрузку
                    return random.choice(valid_instances)
                    
        except Exception as e:
            print(f"Ошибка получения списка серверов: {e}")
            
    # ЗАПАСНОЙ ВАРИАНТ (Если мониторинг не отвечает, пробуем эти хардкодом)
    return "https://cobalt.kwiatekmiki.pl" 

async def get_download_url(url: str):
    # 1. Ищем рабочий сервер
    base_url = await get_working_instance()
    
    if not base_url:
        return {"success": False, "error": "Не удалось найти живой сервер Cobalt."}

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    
    body = {
        "url": url,
        "vCodec": "h264",
    }

    async with aiohttp.ClientSession() as session:
        try:
            # Запрос к найденному серверу
            async with session.post(base_url, json=body, headers=headers, timeout=9) as response:
                
                if response.status != 200:
                    text = await response.text()
                    return {"success": False, "error": f"Сервер {base_url} вернул ошибку: {response.status}"}

                data = await response.json()
                
                link = None
                status = data.get('status')
                
                if status == 'stream' or status == 'redirect':
                    link = data.get('url')
                elif status == 'picker':
                    picker = data.get('picker')
                    if picker: link = picker[0].get('url')
                
                if link:
                    return {"success": True, "url": link}
                else:
                    return {"success": False, "error": f"Сервер ответил, но ссылки нет. Статус: {status}"}
        
        except Exception as e:
            return {"success": False, "error": f"Ошибка соединения с {base_url}: {str(e)}"}

# --- ХЕНДЛЕРЫ ---

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    await message.answer("Я использую динамический поиск серверов. Кидай ссылку!")

@dp.message()
async def download_handler(message: types.Message):
    text = message.text
    if not text or "http" not in text:
        await message.answer("Это не ссылка.")
        return

    status_msg = await message.answer("📡 Ищу рабочий сервер и качаю...")
    
    result = await get_download_url(text)
    
    if result["success"]:
        try:
            await message.answer_video(
                video=result["url"],
                caption="✅ Готово!",
                reply_to_message_id=message.message_id
            )
            await status_msg.delete()
        except Exception as e:
             await status_msg.edit_text(f"📹 Ссылка найдена, но Телеграм не загрузил видео (возможно, слишком большое).\n\n🔗 {result['url']}")
    else:
        await status_msg.edit_text(f"🛑 Ошибка:\n{result['error']}")

# --- WEBHOOK ---

@app.post("/webhook")
async def webhook_handler(request: Request):
    try:
        update_data = await request.json()
        update = Update.model_validate(update_data, context={"bot": bot})
        await dp.feed_update(bot, update)
    except: pass
    return {"status": "ok"}

@app.get("/")
async def index():
    return {"message": "Auto-healing bot running"}