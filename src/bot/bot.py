import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.fsm.storage.memory import MemoryStorage
from redis.asyncio import Redis
from src.core.config import settings
from src.bot.handlers import start, admin, operator, warehouse, investor
from src.bot.middlewares import DatabaseMiddleware, RoleCheckMiddleware
from src.db.database import async_session_maker
from src.utils.logger import setup_logging

# Настройка логирования
logger = setup_logging("bot")


def get_storage():
    """Получение хранилища для FSM"""
    if settings.REDIS_URL and settings.REDIS_URL != "redis://localhost:6379/0":
        try:
            redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
            return RedisStorage(redis)
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}. Using MemoryStorage")
    
    return MemoryStorage()


async def setup_bot_commands(bot: Bot):
    """Установка команд бота"""
    commands = [
        ("start", " Начать работу"),
        ("menu", " Главное меню"),
        ("help", " Помощь"),
        ("profile", " Мой профиль"),
        ("tasks", " Мои задачи"),
        ("stats", " Статистика"),
        ("settings", " Настройки"),
        ("cancel", " Отмена")
    ]
    
    await bot.set_my_commands(commands)


async def on_startup(bot: Bot):
    """Действия при запуске бота"""
    logger.info("Bot is starting...")
    await setup_bot_commands(bot)
    
    # Установка webhook если нужно
    if settings.USE_WEBHOOK and settings.BOT_WEBHOOK_URL:
        await bot.set_webhook(
            settings.BOT_WEBHOOK_URL,
            drop_pending_updates=True
        )
        logger.info(f"Webhook set to: {settings.BOT_WEBHOOK_URL}")
    else:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Using long polling")
    
    # Отправка уведомления админам
    for admin_id in settings.BOT_ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f" {settings.APP_NAME} Bot запущен!\n"
                f"Версия: {settings.APP_VERSION}\n"
                f"Режим: {settings.ENVIRONMENT}"
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")


async def on_shutdown(bot: Bot):
    """Действия при остановке бота"""
    logger.info("Bot is shutting down...")
    
    # Закрытие сессии бота
    await bot.session.close()
    
    # Уведомление админов
    for admin_id in settings.BOT_ADMIN_IDS:
        try:
            await bot.send_message(admin_id, " Bot остановлен")
        except:
            pass


async def main():
    """Основная функция запуска бота"""
    # Инициализация бота
    bot = Bot(
        token=settings.BOT_TOKEN,
        parse_mode="HTML"
    )
    
    # Инициализация диспетчера
    storage = get_storage()
    dp = Dispatcher(storage=storage)
    
    # Регистрация middleware
    dp.message.middleware(DatabaseMiddleware(async_session_maker))
    dp.callback_query.middleware(DatabaseMiddleware(async_session_maker))
    
    # Специальный middleware для проверки ролей
    dp.message.middleware(RoleCheckMiddleware())
    dp.callback_query.middleware(RoleCheckMiddleware())
    
    # Регистрация обработчиков
    dp.include_router(start.router)
    dp.include_router(admin.router)
    dp.include_router(operator.router)
    dp.include_router(warehouse.router)
    dp.include_router(investor.router)
    
    # Регистрация startup/shutdown хендлеров
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    try:
        if settings.USE_WEBHOOK:
            # Webhook mode (для продакшена)
            logger.info("Starting bot in webhook mode...")
            # Здесь должен быть код для webhook
            # Для Railway/Render нужна интеграция с FastAPI
        else:
            # Polling mode (для разработки)
            logger.info("Starting bot in polling mode...")
            await dp.start_polling(
                bot,
                allowed_updates=dp.resolve_used_update_types(),
                drop_pending_updates=True
            )
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        raise
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise
