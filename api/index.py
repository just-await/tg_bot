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

# Список серверов
COBALT_INSTANCES = [
    "https://api.cobalt.tools/api/json",
    "https://co.wuk.sh/api/json",
    "https://cobalt.xyzen.dev/api/json",
]

async def get_download_url(url: str):
    # Добавляем User-Agent, чтобы притвориться браузером (иногда помогает от бана)
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    body = {
        "url": url,
        "vCodec": "h264"
    }

    last_error = ""

    async with aiohttp.ClientSession() as session:
        for api_url in COBALT_INSTANCES:
            try:
                # Увеличим тайм-аут до 8 секунд
                async with session.post(api_url, json=body, headers=headers, timeout=8) as response:
                    
                    if response.status != 200:
                        error_text = await response.text()
                        last_error += f"\n❌ {api_url}: Код {response.status} ({error_text[:50]})"
                        continue

                    data = await response.json()
                    
                    # Пытаемся найти ссылку
                    link = None
                    if data.get('status') == 'stream': link = data.get('url')
                    elif data.get('status') == 'redirect': link = data.get('url')
                    elif data.get('status') == 'picker': link = data.get('picker')[0].get('url')
                    
                    if link:
                        return {"success": True, "url": link}
                    else:
                        last_error += f"\n⚠️ {api_url}: JSON OK, но ссылки нет. Ответ: {str(data)[:50]}"
            
            except Exception as e:
                last_error += f"\n☠️ {api_url}: Ошибка сети {str(e)}"
                
    return {"success": False, "error": last_error}

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    await message.answer("Привет! Кидай ссылку, будем тестировать серверы.")

@dp.message()
async def download_handler(message: types.Message):
    text = message.text
    if not text or "http" not in text:
        await message.answer("Жду ссылку...")
        return

    status_msg = await message.answer("🔎 Диагностика серверов...")
    
    result = await get_download_url(text)
    
    if result["success"]:
        try:
            await message.answer_video(
                video=result["url"],
                caption="✅ Успешно скачано!"
            )
            await status_msg.delete()
        except Exception as e:
             await status_msg.edit_text(f"✅ Ссылка получена, но Телеграм не смог загрузить видео.\nОшибка: {e}\nСсылка: {result['url']}")
    else:
        # ВЫВОДИМ ПОДРОБНЫЙ ОТЧЕТ ОБ ОШИБКАХ
        await status_msg.edit_text(f"🛑 <b>Все серверы отказали. Отчет:</b>\n{result['error']}", parse_mode="HTML")

@app.post("/webhook")
async def webhook_handler(request: Request):
    try:
        update_data = await request.json()
        update = Update.model_validate(update_data, context={"bot": bot})
        await dp.feed_update(bot, update)
    except: pass
    return {"status": "ok"}