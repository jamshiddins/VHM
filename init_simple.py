import asyncio
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from src.db.database import init_db

async def main():
    print(" Инициализация базы данных VendHub...")
    try:
        await init_db()
        print(" База данных успешно инициализирована!")
    except Exception as e:
        print(f" Ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(main())
