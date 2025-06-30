import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# Прямое подключение без использования config
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/vendhub")

# Преобразование для asyncpg
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

print(f"Попытка подключения к: {DATABASE_URL}")

async def test_connection():
    try:
        engine = create_async_engine(DATABASE_URL, echo=True)
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT version()"))
            version = result.scalar()
            print(f" Подключение успешно!")
            print(f"PostgreSQL версия: {version}")
        await engine.dispose()
    except Exception as e:
        print(f" Ошибка подключения: {type(e).__name__}: {e}")

asyncio.run(test_connection())
