from typing import List, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


class MenuKeyboards:
    """Основные меню для разных ролей"""
    
    @staticmethod
    def main_menu(user_roles: List[str]) -> InlineKeyboardMarkup:
        """Главное меню в зависимости от ролей"""
        builder = InlineKeyboardBuilder()
        
        # Общие кнопки для всех
        builder.row(
            InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
            InlineKeyboardButton(text="📊 Статистика", callback_data="stats")
        )
        
        # Кнопки для операторов
        if "operator" in user_roles:
            builder.row(
                InlineKeyboardButton(text="📋 Мои задачи", callback_data="operator:tasks"),
                InlineKeyboardButton(text="🗺 Маршруты", callback_data="operator:routes")
            )
            builder.row(
                InlineKeyboardButton(text="📸 Отчет", callback_data="operator:report")
            )
        
        # Кнопки для склада
        if "warehouse" in user_roles:
            builder.row(
                InlineKeyboardButton(text="📦 Остатки", callback_data="warehouse:inventory"),
                InlineKeyboardButton(text="🚚 Выдача", callback_data="warehouse:issue")
            )
            builder.row(
                InlineKeyboardButton(text="📥 Приемка", callback_data="warehouse:receive"),
                InlineKeyboardButton(text="⚖️ Взвешивание", callback_data="warehouse:weigh")
            )
        
        # Кнопки для менеджеров
        if "manager" in user_roles:
            builder.row(
                InlineKeyboardButton(text="🏪 Автоматы", callback_data="manager:machines"),
                InlineKeyboardButton(text="💰 Финансы", callback_data="manager:finance")
            )
            builder.row(
                InlineKeyboardButton(text="📈 Отчеты", callback_data="manager:reports"),
                InlineKeyboardButton(text="👥 Команда", callback_data="manager:team")
            )
        
        # Кнопки для инвесторов
        if "investor" in user_roles:
            builder.row(
                InlineKeyboardButton(text="💎 Мои инвестиции", callback_data="investor:portfolio"),
                InlineKeyboardButton(text="💸 Выплаты", callback_data="investor:payouts")
            )
            builder.row(
                InlineKeyboardButton(text="📊 Аналитика", callback_data="investor:analytics")
            )
        
        # Кнопки для админов
        if "admin" in user_roles:
            builder.row(
                InlineKeyboardButton(text="⚙️ Админка", callback_data="admin:panel")
            )
        
        # Настройки и помощь
        builder.row(
            InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings"),
            InlineKeyboardButton(text="❓ Помощь", callback_data="help")
        )
        
        return builder.as_markup()
    
    @staticmethod
    def back_button(callback_data: str = "back") -> InlineKeyboardMarkup:
        """Кнопка назад"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data=callback_data)]
        ])
    
    @staticmethod
    def confirm_cancel() -> InlineKeyboardMarkup:
        """Подтверждение/Отмена"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
            ]
        ])


class OperatorKeyboards:
    """Клавиатуры для операторов"""
    
    @staticmethod
    def task_list(tasks: List[dict]) -> InlineKeyboardMarkup:
        """Список задач"""
        builder = InlineKeyboardBuilder()
        
        for task in tasks:
            status_emoji = "✅" if task.get("completed") else "⏳"
            builder.row(
                InlineKeyboardButton(
                    text=f"{status_emoji} {task['machine_name']} - {task['type']}",
                    callback_data=f"task:{task['id']}"
                )
            )
        
        builder.row(
            InlineKeyboardButton(text="🗺 Показать на карте", callback_data="tasks:map"),
            InlineKeyboardButton(text="📊 Статистика", callback_data="tasks:stats")
        )
        builder.row(
            InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu")
        )
        
        return builder.as_markup()
    
    @staticmethod
    def task_actions(task_id: int, completed: bool = False) -> InlineKeyboardMarkup:
        """Действия с задачей"""
        builder = InlineKeyboardBuilder()
        
        if not completed:
            builder.row(
                InlineKeyboardButton(text="📸 Фото до", callback_data=f"task:photo_before:{task_id}"),
                InlineKeyboardButton(text="📸 Фото после", callback_data=f"task:photo_after:{task_id}")
            )
            builder.row(
                InlineKeyboardButton(text="📝 Комментарий", callback_data=f"task:comment:{task_id}"),
                InlineKeyboardButton(text="⚠️ Проблема", callback_data=f"task:problem:{task_id}")
            )
            builder.row(
                InlineKeyboardButton(text="✅ Завершить", callback_data=f"task:complete:{task_id}")
            )
        else:
            builder.row(
                InlineKeyboardButton(text="👁 Просмотр отчета", callback_data=f"task:view:{task_id}")
            )
        
        builder.row(
            InlineKeyboardButton(text="◀️ К списку задач", callback_data="operator:tasks")
        )
        
        return builder.as_markup()


class WarehouseKeyboards:
    """Клавиатуры для склада"""
    
    @staticmethod
    def inventory_categories() -> InlineKeyboardMarkup:
        """Категории товаров"""
        builder = InlineKeyboardBuilder()
        
        categories = [
            ("☕️ Кофе", "coffee"),
            ("🥛 Молоко", "milk"),
            ("🍯 Сиропы", "syrup"),
            ("💧 Вода", "water"),
            ("🥤 Стаканы", "cup"),
            ("🍫 Снеки", "snack"),
            ("📦 Прочее", "other")
        ]
        
        for name, code in categories:
            builder.add(InlineKeyboardButton(text=name, callback_data=f"inventory:cat:{code}"))
        
        builder.adjust(2)
        builder.row(
            InlineKeyboardButton(text="📊 Сводка", callback_data="inventory:summary"),
            InlineKeyboardButton(text="◀️ Назад", callback_data="warehouse:menu")
        )
        
        return builder.as_markup()
    
    @staticmethod
    def weighing_actions() -> InlineKeyboardMarkup:
        """Действия при взвешивании"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📸 Сканировать QR", callback_data="weigh:scan"),
                InlineKeyboardButton(text="🔢 Ввести код", callback_data="weigh:manual")
            ],
            [
                InlineKeyboardButton(text="⚖️ Ввести вес", callback_data="weigh:enter"),
                InlineKeyboardButton(text="📋 История", callback_data="weigh:history")
            ],
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data="warehouse:menu")
            ]
        ])


class FinanceKeyboards:
    """Клавиатуры для финансов"""
    
    @staticmethod
    def transaction_type() -> InlineKeyboardMarkup:
        """Тип транзакции"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="💰 Доход", callback_data="finance:income"),
                InlineKeyboardButton(text="💸 Расход", callback_data="finance:expense")
            ],
            [
                InlineKeyboardButton(text="🔄 Перевод", callback_data="finance:transfer"),
                InlineKeyboardButton(text="🏦 Инкассация", callback_data="finance:collection")
            ],
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data="manager:finance")
            ]
        ])
    
    @staticmethod
    def expense_categories() -> InlineKeyboardMarkup:
        """Категории расходов"""
        builder = InlineKeyboardBuilder()
        
        categories = [
            ("📦 Закупка товаров", "purchase"),
            ("🏢 Аренда", "rent"),
            ("💡 Коммуналка", "utilities"),
            ("💰 Зарплата", "salary"),
            ("🚗 Транспорт", "transport"),
            ("🔧 Ремонт", "repair"),
            ("📱 Связь", "communication"),
            ("📊 Прочее", "other")
        ]
        
        for name, code in categories:
            builder.add(InlineKeyboardButton(text=name, callback_data=f"expense:cat:{code}"))
        
        builder.adjust(2)
        builder.row(
            InlineKeyboardButton(text="◀️ Назад", callback_data="finance:expense")
        )
        
        return builder.as_markup()


class PaginationKeyboard:
    """Клавиатура для пагинации"""
    
    @staticmethod
    def create(
        current_page: int,
        total_pages: int,
        callback_prefix: str,
        additional_buttons: Optional[List[List[InlineKeyboardButton]]] = None
    ) -> InlineKeyboardMarkup:
        """Создание клавиатуры с пагинацией"""
        builder = InlineKeyboardBuilder()
        
        # Кнопки пагинации
        pagination_row = []
        
        if current_page > 1:
            pagination_row.append(
                InlineKeyboardButton(
                    text="◀️",
                    callback_data=f"{callback_prefix}:page:{current_page - 1}"
                )
            )
        
        pagination_row.append(
            InlineKeyboardButton(
                text=f"{current_page}/{total_pages}",
                callback_data="pagination:info"
            )
        )
        
        if current_page < total_pages:
            pagination_row.append(
                InlineKeyboardButton(
                    text="▶️",
                    callback_data=f"{callback_prefix}:page:{current_page + 1}"
                )
            )
        
        builder.row(*pagination_row)
        
        # Дополнительные кнопки
        if additional_buttons:
            for row in additional_buttons:
                builder.row(*row)
        
        return builder.as_markup()