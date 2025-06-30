#!/usr/bin/env python3
"""
Скрипт для создания администратора системы VendHub
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent.parent))

from src.db.database import async_session_maker
from src.db.models.user import User, Role
from src.services.auth import AuthService
from src.services.user import UserService
from src.db.schemas.user import UserCreate
from getpass import getpass


async def create_admin():
    """Создание администратора"""
    print("🚀 Создание администратора VendHub")
    print("-" * 40)
    
    # Ввод данных
    username = input("Username: ").strip()
    if not username:
        print("❌ Username не может быть пустым")
        return
    
    email = input("Email: ").strip()
    if not email:
        print("❌ Email не может быть пустым")
        return
    
    full_name = input("Полное имя: ").strip()
    if not full_name:
        print("❌ Полное имя не может быть пустым")
        return
    
    phone = input("Телефон (с +998): ").strip()
    telegram_id = input("Telegram ID (необязательно): ").strip()
    
    # Ввод пароля
    password = getpass("Пароль (мин. 8 символов): ")
    if len(password) < 8:
        print("❌ Пароль должен быть не менее 8 символов")
        return
    
    password_confirm = getpass("Подтвердите пароль: ")
    if password != password_confirm:
        print("❌ Пароли не совпадают")
        return
    
    print("\n📋 Проверьте данные:")
    print(f"Username: {username}")
    print(f"Email: {email}")
    print(f"Полное имя: {full_name}")
    print(f"Телефон: {phone}")
    print(f"Telegram ID: {telegram_id or 'не указан'}")
    
    confirm = input("\n✅ Создать администратора? (y/n): ")
    if confirm.lower() != 'y':
        print("❌ Отменено")
        return
    
    # Создание администратора
    async with async_session_maker() as session:
        try:
            user_service = UserService(session)
            
            # Проверяем, существует ли роль admin
            admin_role = await session.execute(
                select(Role).where(Role.name == "admin")
            )
            admin_role = admin_role.scalar_one_or_none()
            
            if not admin_role:
                # Создаем роль admin
                admin_role = Role(
                    name="admin",
                    display_name="Администратор",
                    description="Полный доступ к системе",
                    is_system=True
                )
                session.add(admin_role)
                await session.commit()
                print("✅ Создана роль 'admin'")
            
            # Создаем пользователя
            user_data = UserCreate(
                username=username,
                email=email,
                full_name=full_name,
                phone=phone if phone else None,
                telegram_id=int(telegram_id) if telegram_id else None,
                password=password,
                role_names=["admin"]
            )
            
            user = await user_service.create_user(user_data)
            
            # Активируем и верифицируем
            user.is_active = True
            user.is_verified = True
            await session.commit()
            
            print(f"\n✅ Администратор '{username}' успешно создан!")
            print(f"ID: {user.id}")
            print(f"UUID: {user.uuid}")
            
        except Exception as e:
            print(f"\n❌ Ошибка при создании администратора: {e}")
            return


async def list_admins():
    """Список администраторов"""
    async with async_session_maker() as session:
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        
        query = select(User).options(
            selectinload(User.roles)
        ).join(User.roles).where(Role.name == "admin")
        
        result = await session.execute(query)
        admins = result.scalars().all()
        
        if not admins:
            print("❌ Администраторы не найдены")
            return
        
        print("\n👥 Список администраторов:")
        print("-" * 60)
        for admin in admins:
            status = "✅ Активен" if admin.is_active else "❌ Заблокирован"
            print(f"ID: {admin.id} | {admin.username} | {admin.email} | {status}")


async def main():
    """Главная функция"""
    if len(sys.argv) > 1 and sys.argv[1] == "--list":
        await list_admins()
    else:
        await create_admin()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n❌ Отменено пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")