from functools import wraps
from typing import List, Callable, Any
from aiogram.types import Message, CallbackQuery


def require_role(roles: List[str]):
    """
    Декоратор для проверки ролей пользователя.
    
    Args:
        roles: Список разрешенных ролей
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(event: Any, *args, **kwargs):
            # Получаем роли пользователя из контекста
            user_roles = kwargs.get("user_roles", [])
            
            # Проверяем наличие хотя бы одной из требуемых ролей
            if not any(role in user_roles for role in roles):
                error_msg = "❌ У вас нет прав для выполнения этого действия."
                
                if isinstance(event, CallbackQuery):
                    await event.answer(error_msg, show_alert=True)
                    return
                elif isinstance(event, Message):
                    await event.answer(error_msg)
                    return
            
            # Если проверка пройдена, вызываем оригинальную функцию
            return await func(event, *args, **kwargs)
        
        return wrapper
    return decorator


def require_permission(module: str, action: str):
    """
    Декоратор для проверки конкретного разрешения.
    
    Args:
        module: Модуль разрешения
        action: Действие в модуле
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(event: Any, *args, **kwargs):
            # Получаем пользователя из контекста
            user = kwargs.get("user")
            
            if not user or not user.has_permission(module, action):
                error_msg = f"❌ У вас нет разрешения '{module}:{action}'."
                
                if isinstance(event, CallbackQuery):
                    await event.answer(error_msg, show_alert=True)
                    return
                elif isinstance(event, Message):
                    await event.answer(error_msg)
                    return
            
            return await func(event, *args, **kwargs)
        
        return wrapper
    return decorator


class Permissions:
    """Константы разрешений в системе"""
    
    # Машины
    MACHINES_VIEW = ("machines", "view")
    MACHINES_CREATE = ("machines", "create")
    MACHINES_EDIT = ("machines", "edit")
    MACHINES_DELETE = ("machines", "delete")
    
    # Задачи
    TASKS_VIEW = ("tasks", "view")
    TASKS_CREATE = ("tasks", "create")
    TASKS_ASSIGN = ("tasks", "assign")
    TASKS_COMPLETE = ("tasks", "complete")
    
    # Инвентарь
    INVENTORY_VIEW = ("inventory", "view")
    INVENTORY_EDIT = ("inventory", "edit")
    INVENTORY_TRANSFER = ("inventory", "transfer")
    
    # Финансы
    FINANCE_VIEW = ("finance", "view")
    FINANCE_CREATE = ("finance", "create")
    FINANCE_APPROVE = ("finance", "approve")
    FINANCE_EXPORT = ("finance", "export")
    
    # Отчеты
    REPORTS_VIEW = ("reports", "view")
    REPORTS_CREATE = ("reports", "create")
    REPORTS_EXPORT = ("reports", "export")
    
    # Пользователи
    USERS_VIEW = ("users", "view")
    USERS_CREATE = ("users", "create")
    USERS_EDIT = ("users", "edit")
    USERS_DELETE = ("users", "delete")
    USERS_ROLES = ("users", "manage_roles")
    
    # Инвестиции
    INVESTMENTS_VIEW = ("investments", "view")
    INVESTMENTS_CREATE = ("investments", "create")
    INVESTMENTS_APPROVE = ("investments", "approve")
    INVESTMENTS_PAYOUT = ("investments", "payout")


# Роли по умолчанию и их разрешения
DEFAULT_ROLE_PERMISSIONS = {
    "admin": [
        # Полный доступ ко всему
        "*:*"
    ],
    "manager": [
        # Машины
        "machines:view", "machines:create", "machines:edit",
        # Задачи
        "tasks:view", "tasks:create", "tasks:assign",
        # Инвентарь
        "inventory:view", "inventory:edit",
        # Финансы
        "finance:view", "finance:create", "finance:export",
        # Отчеты
        "reports:view", "reports:create", "reports:export",
        # Пользователи
        "users:view", "users:edit",
        # Инвестиции
        "investments:view", "investments:create",
    ],
    "warehouse": [
        # Инвентарь
        "inventory:view", "inventory:edit", "inventory:transfer",
        # Машины (только просмотр)
        "machines:view",
        # Задачи (только просмотр)
        "tasks:view",
        # Отчеты (только инвентарные)
        "reports:view",
    ],
    "operator": [
        # Машины (только просмотр)
        "machines:view",
        # Задачи
        "tasks:view", "tasks:complete",
        # Инвентарь (только просмотр)
        "inventory:view",
    ],
    "investor": [
        # Машины (только свои)
        "machines:view",
        # Финансы (только просмотр)
        "finance:view",
        # Отчеты (только инвестиционные)
        "reports:view",
        # Инвестиции
        "investments:view",
    ]
}