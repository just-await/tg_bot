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

# --- СПИСОК СЕРВЕРОВ (Обновлен под Cobalt v10) ---
# Обрати внимание: в конце ссылок НЕТ "/api/json"
COBALT_INSTANCES = [
    "https://api.cobalt.tools",          # Официальный API
    "https://cobalt.kwiatekmiki.pl",     # Стабильное зеркало
    "https://cobalt.jojo.biz.id",        # Зеркало 2
    "https://cobalt.timos.design",       # Зеркало 3
]

async def get_download_url(url: str):
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    body = {
        "url": url,
        "vCodec": "h264",
        "filenamePattern": "basic" # Нужно для v10
    }

    last_error = ""

    async with aiohttp.ClientSession() as session:
        for base_url in COBALT_INSTANCES:
            try:
                # В новой версии API (v10) мы шлем запрос прямо в корень "/"
                # или добавляем "/api/json" только для старых версий.
                # Большинство серверов сейчас перешли на v10, поэтому пробуем корень.
                
                # Попробуем сформировать корректный URL
                # Некоторые инстансы требуют / на конце, некоторые нет.
                request_url = base_url if base_url.endswith("/") else f"{base_url}/"
                
                # ВАЖНО: для v7 было /api/json, для v10 просто POST на корень
                # Но на всякий случай обработаем гибридный вариант
                
                async with session.post(request_url, json=body, headers=headers, timeout=9) as response:
                    
                    if response.status != 200:
                        # Если корень не сработал, попробуем старый путь (для совместимости)
                        if response.status == 404:
                            # Логика повтора для старого API опущена для краткости, 
                            # так как мы используем свежие серверы.
                            pass
                            
                        err_text = await response.text()
                        last_error += f"\n❌ {base_url}: {response.status}"
                        continue

                    data = await response.json()
                    
                    # Логика парсинга ответа (она похожа)
                    link = None
                    if data.get('status') == 'stream': link = data.get('url')
                    elif data.get('status') == 'redirect': link = data.get('url')
                    elif data.get('status') == 'picker': link = data.get('picker')[0].get('url')
                    # В v10 иногда ссылка лежит прямо в корне json, если успех? 
                    # Нет, структура 'status' сохраняется.
                    
                    if link:
                        return {"success": True, "url": link}
                    else:
                        last_error += f"\n⚠️ {base_url}: Ответ OK, но ссылки нет."
            
            except Exception as e:
                last_error += f"\n☠️ {base_url}: {str(e)}"
                
    return {"success": False, "error": last_error}

# --- ХЕНДЛЕРЫ ---

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    await message.answer("Версия бота: Cobalt v10.\nКидай ссылку на TikTok/Reels!")

@dp.message()
async def download_handler(message: types.Message):
    text = message.text
    if not text or "http" not in text:
        await message.answer("Это не ссылка.")
        return

    status_msg = await message.answer("🔎 Ищу видео (v10)...")
    
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
             await status_msg.edit_text(f"✅ Ссылка есть, но Телеграм не скачал: {e}")
    else:
        await status_msg.edit_text(f"🛑 <b>Ошибка скачивания:</b>\n{result['error']}", parse_mode="HTML")

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
    return {"message": "Bot is running v10"}