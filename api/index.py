import os
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.types import Update

# --- НАСТРОЙКИ ---
# Токен будем брать из переменных окружения Vercel (безопасность!)
TOKEN = os.getenv("BOT_TOKEN")

app = FastAPI()
bot = Bot(TOKEN)
dp = Dispatcher()

# --- ЛОГИКА БОТА (Та же самая) ---

@dp.message()
async def echo_handler(message: types.Message):
    user = message.from_user
    
    info_text = (
        f"🕵️‍♂️ <b>Инфо о пользователе:</b>\n\n"
        f"🆔 <b>ID:</b> <code>{user.id}</code>\n"
        f"👤 <b>Имя:</b> {user.first_name}\n"
        f"🔗 <b>Username:</b> @{user.username if user.username else 'Нет'}\n"
        f"🌐 <b>Язык:</b> {user.language_code}\n"
        f"💎 <b>Premium:</b> {'Да' if user.is_premium else 'Нет'}\n"
        f"🤖 <b>Это бот?</b> {'Да' if user.is_bot else 'Нет'}"
    )
    
    # ВАЖНО: На Vercel лучше использовать bot.send_message вместо message.answer,
    # чтобы избежать ошибок контекста, хотя answer тоже может работать.
    await bot.send_message(chat_id=message.chat.id, text=info_text, parse_mode="HTML")

# --- СЛУЖЕБНЫЕ ФУНКЦИИ ---

@app.post("/webhook")
async def webhook_handler(request: Request):
    """
    Сюда приходят обновления от Telegram
    """
    # Получаем JSON из запроса
    update_data = await request.json()
    # Превращаем JSON в объект Update
    update = Update.model_validate(update_data, context={"bot": bot})
    # Передаем обновление в диспетчер Aiogram
    await dp.feed_update(bot, update)
    return {"status": "ok"}

@app.get("/")
async def index():
    return {"message": "Bot is running on Vercel!"}