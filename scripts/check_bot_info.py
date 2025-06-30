# scripts/check_bot_info.py
"""
Скрипт для получения информации о Telegram боте
"""
import asyncio
import os
from aiogram import Bot
from dotenv import load_dotenv
import json

load_dotenv()

async def get_bot_info():
    """Получение полной информации о боте"""
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN не найден!")
        return
    
    bot = Bot(token=BOT_TOKEN)
    
    try:
        # Информация о боте
        me = await bot.get_me()
        print(" ИНФОРМАЦИЯ О БОТЕ:")
        print(f"   ID: {me.id}")
        print(f"   Username: @{me.username}")
        print(f"   Имя: {me.first_name}")
        print(f"   Поддержка inline: {me.supports_inline_queries}")
        
        # Webhook
        webhook = await bot.get_webhook_info()
        print(f"\n WEBHOOK:")
        print(f"   URL: {webhook.url or 'Не установлен'}")
        print(f"   Pending updates: {webhook.pending_update_count}")
        
        # Команды
        commands = await bot.get_my_commands()
        print(f"\n📋 КОМАНДЫ ({len(commands)}):")
        for cmd in commands:
            print(f"   /{cmd.command} - {cmd.description}")
        
        # Ссылка для добавления в группу
        print(f"\n ССЫЛКИ:")
        print(f"   Прямая: https://t.me/{me.username}")
        print(f"   Добавить в группу: https://t.me/{me.username}?startgroup=true")
        print(f"   Админ панель: https://t.me/{me.username}?start=admin")
        
    except Exception as e:
        print(f" Ошибка: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(get_bot_info())
