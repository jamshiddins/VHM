from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from src.services.user import UserService
import logging

logger = logging.getLogger(__name__)


class DatabaseMiddleware(BaseMiddleware):
    """Middleware для работы с базой данных"""
    
    def __init__(self, session_factory: async_sessionmaker):
        self.session_factory = session_factory
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        async with self.session_factory() as session:
            data["session"] = session
            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception as e:
                await session.rollback()
                logger.error(f"Database error: {e}")
                raise
            finally:
                await session.close()


class RoleCheckMiddleware(BaseMiddleware):
    """Middleware для проверки ролей пользователя"""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Получаем пользователя из события
        user_id = None
        
        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None
        
        if user_id and "session" in data:
            session: AsyncSession = data["session"]
            user_service = UserService(session)
            user = await user_service.get_by_telegram_id(user_id)
            
            if user:
                data["user"] = user
                data["user_roles"] = [role.name for role in user.roles]
            else:
                data["user"] = None
                data["user_roles"] = []
        
        return await handler(event, data)


class LoggingMiddleware(BaseMiddleware):
    """Middleware для логирования"""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user_info = ""
        
        if isinstance(event, Message):
            user_info = f"User: {event.from_user.id} (@{event.from_user.username})" if event.from_user else "Unknown user"
            logger.info(f"Message from {user_info}: {event.text[:50] if event.text else 'No text'}")
        elif isinstance(event, CallbackQuery):
            user_info = f"User: {event.from_user.id} (@{event.from_user.username})" if event.from_user else "Unknown user"
            logger.info(f"Callback from {user_info}: {event.data}")
        
        try:
            result = await handler(event, data)
            return result
        except Exception as e:
            logger.error(f"Error handling {type(event).__name__} from {user_info}: {e}")
            raise


class ThrottlingMiddleware(BaseMiddleware):
    """Middleware для ограничения частоты запросов"""
    
    def __init__(self, rate_limit: int = 3):
        self.rate_limit = rate_limit
        self.user_timestamps: Dict[int, list] = {}
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user_id = None
        
        if isinstance(event, (Message, CallbackQuery)):
            user_id = event.from_user.id if event.from_user else None
        
        if user_id:
            from datetime import datetime, timedelta
            
            now = datetime.now()
            
            # Очищаем старые записи
            if user_id in self.user_timestamps:
                self.user_timestamps[user_id] = [
                    ts for ts in self.user_timestamps[user_id]
                    if now - ts < timedelta(seconds=1)
                ]
            else:
                self.user_timestamps[user_id] = []
            
            # Проверяем лимит
            if len(self.user_timestamps[user_id]) >= self.rate_limit:
                if isinstance(event, CallbackQuery):
                    await event.answer(
                        "⚠️ Слишком много запросов. Подождите немного.",
                        show_alert=True
                    )
                elif isinstance(event, Message):
                    await event.answer("⚠️ Слишком много запросов. Подождите немного.")
                return
            
            # Добавляем timestamp
            self.user_timestamps[user_id].append(now)
        
        return await handler(event, data)