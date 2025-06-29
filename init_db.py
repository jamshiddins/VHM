"""Инициализация базы данных"""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

from src.db.database import engine, Base
from sqlalchemy import text

# Импортируем все модели напрямую
from src.db.models.user import User
from src.db.models.machine import Machine
from src.db.models.product import Product
from src.db.models.task import Task
from src.db.models.recipe import Recipe
from src.db.models.route import Route
from src.db.models.investment import Investment
from src.db.models.finance import FinanceTransaction

async def init_db():
    """Создание таблиц в БД"""
    print(" Создание таблиц в базе данных...")
    
    try:
        # Создаем все таблицы
        async with engine.begin() as conn:
            # Сначала удаляем все таблицы (для чистой установки)
            await conn.run_sync(Base.metadata.drop_all)
            # Создаем таблицы заново
            await conn.run_sync(Base.metadata.create_all)
            
        print(" Таблицы успешно созданы!")
        
        # Создаем начальные данные
        async with engine.begin() as conn:
            # Для SQLite используем другой синтаксис
            if "sqlite" in str(engine.url):
                await conn.execute(text("""
                    INSERT OR IGNORE INTO users (telegram_id, username, full_name, role, is_active)
                    VALUES (1, 'admin', 'Администратор', 'admin', 1)
                """))
            else:
                await conn.execute(text("""
                    INSERT INTO users (telegram_id, username, full_name, role, is_active)
                    VALUES (1, 'admin', 'Администратор', 'admin', true)
                    ON CONFLICT (telegram_id) DO NOTHING
                """))
            
            print(" Начальные данные загружены!")
            
    except Exception as e:
        print(f" Ошибка при создании БД: {e}")
        raise
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(init_db())