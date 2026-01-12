import os
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

# --- СПИСОК ВЫЖИВШИХ (Hardcoded List) ---
# Это серверы, которые работают прямо сейчас, в обход мониторингов.
# Мы будем пробовать их по очереди.
COBALT_INSTANCES = [
    "https://api.notsobad.app",       # Часто живой
    "https://cobalt.smartcode.nl",    # Европейское зеркало
    "https://cobalt.q-s.pl",          # Польское зеркало
    "https://cobalt.rudart.cn",       # Китайское зеркало (иногда медленное, но рабочее)
    "https://api.cool.bio",           # Альтернатива
]

async def get_download_url(url: str):
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Origin": "https://cobalt.tools",
        "Referer": "https://cobalt.tools/"
    }
    
    body = {
        "url": url,
        "vCodec": "h264"
    }

    last_error = ""

    async with aiohttp.ClientSession() as session:
        # Перебираем список вручную
        for base_url in COBALT_INSTANCES:
            try:
                # Формируем URL. Убираем слеш на конце, если есть
                target_url = base_url.rstrip("/")
                
                # Ставим короткий таймаут (5 сек), чтобы быстро перескакивать мертвые
                async with session.post(target_url, json=body, headers=headers, timeout=5) as response:
                    
                    if response.status != 200:
                        # Если сервер вернул ошибку, просто идем к следующему
                        last_error += f"\n❌ {base_url}: HTTP {response.status}"
                        continue

                    data = await response.json()
                    
                    # Пытаемся достать ссылку
                    link = None
                    status = data.get('status')
                    
                    if status == 'stream' or status == 'redirect':
                        link = data.get('url')
                    elif status == 'picker':
                        picker = data.get('picker')
                        if picker: link = picker[0].get('url')
                    
                    if link:
                        return {"success": True, "url": link}
            
            except Exception as e:
                # Если сервер вообще не отвечает (DNS error), идем дальше
                last_error += f"\n☠️ {base_url}: Error"
                continue
                
    return {"success": False, "error": last_error}

# --- ХЕНДЛЕРЫ ---

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    await message.answer("Режим выживания активирован. Кидай ссылку!")

@dp.message()
async def download_handler(message: types.Message):
    text = message.text
    if not text or "http" not in text:
        await message.answer("Это не ссылка.")
        return

    status_msg = await message.answer("🔄 Перебираю рабочие зеркала...")
    
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
             await status_msg.edit_text(f"📹 Ссылка найдена, но загрузка не удалась.\n{result['url']}")
    else:
        # Если все 5 серверов лежат
        await status_msg.edit_text(f"🛑 Все зеркала недоступны.\nБесплатные API сейчас штормит.\n{result['error']}")

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
    return {"message": "Survival mode active"}