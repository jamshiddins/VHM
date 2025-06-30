# scripts/setup_webhook.py
"""
Скрипт для настройки webhook Telegram бота
"""
import asyncio
import os
import sys
from aiogram import Bot
from dotenv import load_dotenv

load_dotenv()

async def setup_webhook(webhook_url: str = None):
    """Настройка webhook"""
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    if not BOT_TOKEN:
        print(" BOT_TOKEN не найден!")
        return
    
    if not webhook_url:
        webhook_url = os.getenv("WEBHOOK_URL", "https://api.vendhub.uz/webhook")
    
    bot = Bot(token=BOT_TOKEN)
    
    try:
        # Удаление старого webhook
        await bot.delete_webhook(drop_pending_updates=True)
        print(" Старый webhook удален")
        
        # Установка нового
        await bot.set_webhook(webhook_url)
        print(f" Webhook установлен: {webhook_url}")
        
        # Проверка
        info = await bot.get_webhook_info()
        print(f" Статус: {info.url}")
        print(f"   Pending updates: {info.pending_update_count}")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        await bot.session.close()

async def remove_webhook():
    """Удаление webhook"""
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    if not BOT_TOKEN:
        print(" BOT_TOKEN не найден!")
        return
    
    bot = Bot(token=BOT_TOKEN)
    
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        print(" Webhook удален")
    except Exception as e:
        print(f" Ошибка: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "remove":
            asyncio.run(remove_webhook())
        else:
            asyncio.run(setup_webhook(sys.argv[1]))
    else:
        asyncio.run(setup_webhook())
