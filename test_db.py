import asyncio
from sqlalchemy import text
from src.db.database import engine

async def test_connection():
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            print(" Подключение к БД успешно!")
    except Exception as e:
        print(f" Ошибка подключения: {e}")

asyncio.run(test_connection())
