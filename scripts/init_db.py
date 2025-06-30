#!/usr/bin/env python3
"""
Скрипт для инициализации базы данных VendHub
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent.parent))

from src.db.database import engine, init_db
from src.db.base import Base
from src.db.models import *  # noqa: F401, F403
from src.core.permissions import DEFAULT_ROLE_PERMISSIONS
from sqlalchemy import text


async def create_tables():
    """Создание таблиц в БД"""
    print("📊 Создание таблиц базы данных...")
    
    try:
        await init_db()
        print("✅ Таблицы успешно созданы")
    except Exception as e:
        print(f"❌ Ошибка при создании таблиц: {e}")
        return False
    
    return True


async def create_default_roles():
    """Создание ролей по умолчанию"""
    print("\n👥 Создание ролей по умолчанию...")
    
    from src.db.database import async_session_maker
    from src.db.models.user import Role, Permission
    from sqlalchemy import select
    
    async with async_session_maker() as session:
        try:
            # Создаем роли
            roles_data = [
                ("admin", "Администратор", "Полный доступ к системе"),
                ("manager", "Менеджер", "Управление автоматами и финансами"),
                ("warehouse", "Склад", "Управление запасами"),
                ("operator", "Оператор", "Обслуживание автоматов"),
                ("investor", "Инвестор", "Просмотр инвестиций и отчетов")
            ]
            
            for role_name, display_name, description in roles_data:
                # Проверяем существование роли
                existing_role = await session.execute(
                    select(Role).where(Role.name == role_name)
                )
                if not existing_role.scalar_one_or_none():
                    role = Role(
                        name=role_name,
                        display_name=display_name,
                        description=description,
                        is_system=True
                    )
                    session.add(role)
                    print(f"  ✅ Создана роль: {role_name}")
            
            await session.commit()
            
            # Создаем разрешения
            print("\n🔐 Создание разрешений...")
            permissions_set = set()
            
            for role_name, permissions in DEFAULT_ROLE_PERMISSIONS.items():
                for perm in permissions:
                    if perm == "*:*":
                        continue  # Особое разрешение для админа
                    
                    module, action = perm.split(":")
                    permissions_set.add((module, action))
            
            for module, action in permissions_set:
                # Проверяем существование разрешения
                existing_perm = await session.execute(
                    select(Permission).where(
                        Permission.module == module,
                        Permission.action == action
                    )
                )
                if not existing_perm.scalar_one_or_none():
                    permission = Permission(
                        module=module,
                        action=action,
                        description=f"{action.title()} {module}"
                    )
                    session.add(permission)
            
            await session.commit()
            print("  ✅ Разрешения созданы")
            
            # Назначаем разрешения ролям
            print("\n🔗 Назначение разрешений ролям...")
            
            for role_name, permissions in DEFAULT_ROLE_PERMISSIONS.items():
                if role_name == "admin":
                    continue  # Админ имеет все права по умолчанию
                
                # Получаем роль
                role_result = await session.execute(
                    select(Role).where(Role.name == role_name)
                )
                role = role_result.scalar_one_or_none()
                
                if role:
                    # Получаем разрешения
                    for perm_str in permissions:
                        module, action = perm_str.split(":")
                        perm_result = await session.execute(
                            select(Permission).where(
                                Permission.module == module,
                                Permission.action == action
                            )
                        )
                        permission = perm_result.scalar_one_or_none()
                        
                        if permission and permission not in role.permissions:
                            role.permissions.append(permission)
                    
                    print(f"  ✅ Назначены разрешения для роли: {role_name}")
            
            await session.commit()
            
        except Exception as e:
            print(f"❌ Ошибка при создании ролей: {e}")
            return False
    
    return True


async def create_default_data():
    """Создание начальных данных"""
    print("\n📦 Создание начальных данных...")
    
    from src.db.database import async_session_maker
    from src.db.models.finance import FinanceAccount
    from src.db.models.inventory import Warehouse
    
    async with async_session_maker() as session:
        try:
            # Создаем основные финансовые счета
            accounts = [
                ("cash_main", "Основная касса", "cash"),
                ("bank_main", "Основной банковский счет", "bank"),
                ("payme", "PayMe кошелек", "wallet"),
                ("click", "Click кошелек", "wallet"),
                ("uzum", "Uzum кошелек", "wallet")
            ]
            
            for code, name, acc_type in accounts:
                account = FinanceAccount(
                    code=code,
                    name=name,
                    type=acc_type,
                    currency="UZS",
                    balance=0,
                    is_active=True
                )
                session.add(account)
            
            print("  ✅ Созданы финансовые счета")
            
            # Создаем основной склад
            warehouse = Warehouse(
                code="main",
                name="Основной склад",
                address="г. Ташкент",
                is_active=True
            )
            session.add(warehouse)
            print("  ✅ Создан основной склад")
            
            await session.commit()
            
        except Exception as e:
            print(f"❌ Ошибка при создании начальных данных: {e}")
            return False
    
    return True


async def main():
    """Главная функция"""
    print("🚀 Инициализация базы данных VendHub")
    print("=" * 50)
    
    # Проверка подключения к БД
    print("\n🔌 Проверка подключения к базе данных...")
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            print("✅ Подключение к БД успешно")
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        print("\nПроверьте настройки DATABASE_URL в .env файле")
        return
    
    # Создание таблиц
    if not await create_tables():
        return
    
    # Создание ролей и разрешений
    if not await create_default_roles():
        return
    
    # Создание начальных данных
    if not await create_default_data():
        return
    
    print("\n✅ База данных успешно инициализирована!")
    print("\nСледующие шаги:")
    print("1. Создайте администратора: python scripts/create_admin.py")
    print("2. Запустите приложение: uvicorn src.main:app --reload")
    print("3. Запустите бота: python -m src.bot.bot")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n❌ Отменено пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")