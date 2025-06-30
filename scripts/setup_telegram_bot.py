# scripts/setup_telegram_bot.py
"""
Скрипт для настройки Telegram бота в production
"""
import asyncio
import logging
from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeDefault
import os
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def setup_bot_commands(bot: Bot):
    """Установка команд бота"""
    commands = [
        BotCommand(command="start", description="🚀 Начать работу"),
        BotCommand(command="menu", description="📋 Главное меню"),
        BotCommand(command="profile", description="👤 Мой профиль"),
        BotCommand(command="help", description=" Помощь"),
        BotCommand(command="operator", description=" Меню оператора"),
        BotCommand(command="warehouse", description=" Меню склада"),
        BotCommand(command="manager", description="👔 Меню менеджера"),
        BotCommand(command="admin", description="👨‍💼 Меню администратора"),
        BotCommand(command="cancel", description=" Отменить операцию"),
    ]
    
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
    logger.info("✅ Команды бота установлены")


async def setup_webhook(bot: Bot, webhook_url: str):
    """Настройка webhook для production"""
    # Удаление старого webhook
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Установка нового webhook
    await bot.set_webhook(
        url=webhook_url,
        max_connections=100,
        drop_pending_updates=True
    )
    
    # Проверка webhook
    webhook_info = await bot.get_webhook_info()
    logger.info(f" Webhook установлен: {webhook_info.url}")
    logger.info(f"   Pending updates: {webhook_info.pending_update_count}")
    

async def setup_bot_info(bot: Bot):
    """Обновление информации о боте"""
    # Установка описания
    await bot.set_my_description(
        description=" VendHub Bot - система управления сетью вендинговых автоматов.\n\n"
                   "Функции:\n"
                   "  Управление задачами\n"
                   "  Учет товаров и склад\n"
                   "  Инкассация\n"
                   "  Отчеты и аналитика\n\n"
                   "Начните с команды /start"
    )
    
    # Установка краткого описания
    await bot.set_my_short_description(
        short_description="Система управления вендинговыми автоматами"
    )
    
    logger.info(" Информация о боте обновлена")


async def check_bot_health(bot: Bot):
    """Проверка здоровья бота"""
    try:
        me = await bot.get_me()
        logger.info(f" Бот работает: @{me.username}")
        logger.info(f"   ID: {me.id}")
        logger.info(f"   Имя: {me.first_name}")
        
        # Проверка webhook
        webhook = await bot.get_webhook_info()
        if webhook.url:
            logger.info(f" Webhook активен: {webhook.url}")
        else:
            logger.warning("  Webhook не настроен")
            
        return True
    except Exception as e:
        logger.error(f" Ошибка проверки бота: {e}")
        return False


async def main():
    """Основная функция настройки"""
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://api.vendhub.uz/webhook")
    
    if not BOT_TOKEN:
        logger.error(" BOT_TOKEN не найден в переменных окружения!")
        return
    
    bot = Bot(token=BOT_TOKEN)
    
    try:
        logger.info(" Начинаем настройку Telegram бота...")
        
        # Проверка бота
        if not await check_bot_health(bot):
            return
        
        # Установка команд
        await setup_bot_commands(bot)
        
        # Обновление информации
        await setup_bot_info(bot)
        
        # Настройка webhook (только для production)
        if os.getenv("ENVIRONMENT") == "production":
            await setup_webhook(bot, WEBHOOK_URL)
        else:
            logger.info("ℹ  Webhook не настраивается (не production)")
        
        logger.info(" Настройка бота завершена успешно!")
        
    except Exception as e:
        logger.error(f" Ошибка настройки: {e}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
