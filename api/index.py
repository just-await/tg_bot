import os
import aiohttp
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import Update

TOKEN = os.getenv("BOT_TOKEN")
app = FastAPI()
bot = Bot(TOKEN)
dp = Dispatcher()

# --- СПИСОК ЖИВЫХ СЕРВЕРОВ (Январь 2025) ---
# Если какие-то умрут, бот автоматически перейдет к следующему.
COBALT_INSTANCES = [
    "https://api.notsobad.app",      # Очень стабильный
    "https://cobalt.pub",            # Популярное зеркало
    "https://cobalt.moskas.io",      # Надежный
    "https://api.cobalt.tools",      # Официальный (часто капризный)
    "https://cobalt.frontend.ju.mp"  # Запасной
]

async def get_download_url(url: str):
    # Заголовки, максимально похожие на настоящий браузер
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Origin": "https://cobalt.tools",
        "Referer": "https://cobalt.tools/"
    }
    
    body = {
        "url": url,
        "vCodec": "h264", 
        # vCodec h264 обязателен, иначе Телеграм не поймет видео
    }

    last_error = ""

    async with aiohttp.ClientSession() as session:
        for base_url in COBALT_INSTANCES:
            try:
                # В Cobalt v10+ запрос шлется методом POST прямо в корень "/"
                # Убираем слеш в конце base_url если он есть, чтобы не было двойного
                api_url = base_url.rstrip("/")
                
                # Ставим таймаут 7 секунд
                async with session.post(api_url, json=body, headers=headers, timeout=7) as response:
                    
                    if response.status != 200:
                        err_text = await response.text()
                        # Сокращаем текст ошибки для логов
                        last_error += f"\n❌ {base_url}: HTTP {response.status}"
                        continue

                    data = await response.json()
                    
                    # Пытаемся достать ссылку
                    link = None
                    status = data.get('status')
                    
                    if status == 'stream' or status == 'redirect':
                        link = data.get('url')
                    elif status == 'picker':
                        # Если видео состоит из нескольких вариантов, берем первый
                        picker = data.get('picker')
                        if picker and len(picker) > 0:
                            link = picker[0].get('url')
                    
                    if link:
                        return {"success": True, "url": link}
                    else:
                        last_error += f"\n⚠️ {base_url}: JSON OK, ссылки нет."
            
            except Exception as e:
                last_error += f"\n☠️ {base_url}: {str(e)[:50]}" # Обрезаем длинные ошибки
                
    return {"success": False, "error": last_error}

# --- ХЕНДЛЕРЫ ---

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    await message.answer("Привет! Я готов качать видео. Кидай ссылку!")

@dp.message()
async def download_handler(message: types.Message):
    text = message.text
    if not text or "http" not in text:
        await message.answer("Это не ссылка.")
        return

    status_msg = await message.answer("🔎 Перебираю серверы...")
    
    result = await get_download_url(text)
    
    if result["success"]:
        try:
            # Сначала пробуем отправить как видео
            await message.answer_video(
                video=result["url"],
                caption="✅ Видео скачано!",
                reply_to_message_id=message.message_id
            )
            await status_msg.delete()
        except Exception as e:
             # Если видео слишком большое или формат странный, кидаем просто ссылку
             await status_msg.edit_text(f"📹 Видео найдено, но Телеграм не может его загрузить сам.\nВот прямая ссылка:\n{result['url']}")
    else:
        await status_msg.edit_text(f"🛑 <b>Не удалось скачать:</b>\n{result['error']}", parse_mode="HTML")

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
    return {"message": "Bot is active"}