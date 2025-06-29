"""Тест подключения к БД и базовых операций"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.db.database import AsyncSessionLocal
from src.db.init_models import User
from sqlalchemy import select

async def test_connection():
    """Тестируем подключение к БД"""
    print(" Тестируем подключение к базе данных...")
    
    try:
        async with AsyncSessionLocal() as session:
            # Пробуем выполнить простой запрос
            result = await session.execute(select(User).limit(1))
            users = result.scalars().all()
            
            print(f" Подключение успешно! Найдено пользователей: {len(users)}")
            
            if users:
                user = users[0]
                print(f"   - Пользователь: {user.username} (ID: {user.id})")
                
    except Exception as e:
        print(f" Ошибка подключения: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(test_connection())