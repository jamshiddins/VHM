import logging
import sys
from pathlib import Path
from loguru import logger
from src.core.config import settings


def setup_logging(module_name: str = None) -> logging.Logger:
    """
    Настройка логирования для модуля.
    
    Args:
        module_name: Имя модуля для логирования
    
    Returns:
        Logger instance
    """
    # Удаляем стандартный обработчик loguru
    logger.remove()
    
    # Формат логов
    log_format = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    
    # Консольный вывод
    logger.add(
        sys.stdout,
        format=log_format,
        level=settings.LOG_LEVEL,
        colorize=True,
        backtrace=True,
        diagnose=settings.DEBUG
    )
    
    # Файловый вывод
    if settings.LOG_FILE:
        logger.add(
            settings.LOG_FILE,
            format=log_format,
            level=settings.LOG_LEVEL,
            rotation="10 MB",
            retention="7 days",
            compression="zip",
            backtrace=True,
            diagnose=settings.DEBUG
        )
    
    # JSON формат для продакшена
    if settings.LOG_FORMAT == "json" and settings.is_production:
        logger.add(
            sys.stdout,
            format="{message}",
            level=settings.LOG_LEVEL,
            serialize=True
        )
    
    # Интеграция с стандартным logging
    class InterceptHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            # Get corresponding Loguru level if it exists
            try:
                level = logger.level(record.levelname).name
            except ValueError:
                level = record.levelno

            # Find caller from where originated the logged message
            frame, depth = logging.currentframe(), 2
            while frame.f_code.co_filename == logging.__file__:
                frame = frame.f_back
                depth += 1

            logger.opt(depth=depth, exception=record.exc_info).log(
                level, record.getMessage()
            )
    
    # Настройка стандартного логгера
    logging.basicConfig(handlers=[InterceptHandler()], level=0)
    
    # Настройка логгеров сторонних библиотек
    for logger_name in ["uvicorn", "uvicorn.access", "sqlalchemy.engine"]:
        logging.getLogger(logger_name).handlers = [InterceptHandler()]
    
    # Возвращаем logger для модуля
    if module_name:
        return logger.bind(module=module_name)
    return logger


# Создаем логгеры для разных модулей
api_logger = setup_logging("api")
bot_logger = setup_logging("bot")
db_logger = setup_logging("database")
service_logger = setup_logging("service")