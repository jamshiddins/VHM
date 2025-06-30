import asyncio
import os
from urllib.parse import quote_plus
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# Загружаем переменные из .env
load_dotenv()

# Получаем URL из окружения
DATABASE_URL = os.getenv("DATABASE_URL")
print(f"Исходный URL: {DATABASE_URL}")

# Парсим и кодируем пароль
if DATABASE_URL:
    # Извлекаем пароль
    if "@" in DATABASE_URL and ":" in DATABASE_URL.split("@")[0]:
        parts = DATABASE_URL.split("@")
        auth_parts = parts[0].split(":")
        if len(auth_parts) >= 3:
            password = ":".join(auth_parts[2:])  # Пароль может содержать ":"
            encoded_password = quote_plus(password)
            username = auth_parts[1].replace("//", "")
            host_and_db = "@".join(parts[1:])
            DATABASE_URL = f"postgresql://{username}:{encoded_password}@{host_and_db}"

# Преобразование для asyncpg
if DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

print(f"Подключение к: {DATABASE_URL}")

async def test_connection():
    try:
        # Добавляем параметры для решения проблем с IPv6
        engine = create_async_engine(
            DATABASE_URL, 
            echo=True,
            connect_args={
                "server_settings": {"jit": "off"},
                "command_timeout": 60,
            }
        )
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT version()"))
            version = result.scalar()
            print(f" Подключение успешно!")
            print(f"PostgreSQL версия: {version}")
        await engine.dispose()
    except Exception as e:
        print(f" Ошибка подключения: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if DATABASE_URL:
    asyncio.run(test_connection())
else:
    print(" DATABASE_URL не найден в переменных окружения")
