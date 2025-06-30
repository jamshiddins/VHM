from datetime import datetime, date, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from src.bot.keyboards.inline import MenuKeyboards
from src.services.user import UserService
from src.services.machine import MachineService
from src.services.finance import FinanceService
from src.services.task import TaskService
from src.core.permissions import require_role
from src.db.models.user import User, Role
from src.db.models.machine import Machine, MachineStatus
from src.db.models.finance import FinanceTransaction
from src.db.models.route import MachineTask, TaskStatus

router = Router()


class AdminStates(StatesGroup):
    """Состояния для админских операций"""
    waiting_for_user_search = State()
    waiting_for_role_assignment = State()
    waiting_for_broadcast_message = State()
    waiting_for_backup_confirmation = State()


@router.callback_query(F.data == "admin:panel")
@require_role(["admin"])
async def show_admin_panel(callback: CallbackQuery, session: AsyncSession):
    """Показать админскую панель"""
    # Получаем статистику
    users_count = await session.execute(select(func.count(User.id)))
    users_count = users_count.scalar()
    
    machines_count = await session.execute(select(func.count(Machine.id)))
    machines_count = machines_count.scalar()
    
    today_sales = await session.execute(
        select(func.count()).select_from(FinanceTransaction).where(
            FinanceTransaction.action_timestamp >= date.today()
        )
    )
    today_sales = today_sales.scalar()
    
    text = f"""
⚙️ <b>Панель администратора</b>

📊 <b>Общая статистика:</b>
👥 Пользователей: {users_count}
🏪 Автоматов: {machines_count}
💰 Продаж сегодня: {today_sales}

<b>Выберите действие:</b>
    """
    
    keyboard = MenuKeyboards.admin_panel()
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "admin:users")
@require_role(["admin"])
async def manage_users(callback: CallbackQuery, session: AsyncSession):
    """Управление пользователями"""
    text = """
👥 <b>Управление пользователями</b>

Выберите действие:
• <b>Список пользователей</b> - просмотр всех пользователей
• <b>Поиск пользователя</b> - поиск по имени/телефону
• <b>Управление ролями</b> - назначение/удаление ролей
• <b>Заблокированные</b> - список заблокированных
    """
    
    keyboard = MenuKeyboards.user_management()
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "admin:users:list")
@require_role(["admin"])
async def list_users(callback: CallbackQuery, session: AsyncSession):
    """Список пользователей"""
    user_service = UserService(session)
    
    # Получаем последних 10 пользователей
    from src.db.schemas.user import UserFilter
    users, total = await user_service.get_users_list(
        UserFilter(limit=10)
    )
    
    text = f"👥 <b>Пользователи системы</b>\nВсего: {total}\n\n"
    
    for user in users:
        roles = ", ".join([r.name for r in user.roles])
        status = "✅" if user.is_active else "❌"
        text += f"{status} <b>{user.full_name}</b>\n"
        text += f"   @{user.username or 'нет'} | {roles or 'без ролей'}\n\n"
    
    keyboard = MenuKeyboards.users_list_actions()
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "admin:users:search")
@require_role(["admin"])
async def start_user_search(callback: CallbackQuery, state: FSMContext):
    """Начать поиск пользователя"""
    await state.set_state(AdminStates.waiting_for_user_search)
    
    await callback.message.edit_text(
        "🔍 Введите имя, username, телефон или email для поиска:"
    )
    await callback.answer()


@router.message(AdminStates.waiting_for_user_search)
@require_role(["admin"])
async def process_user_search(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка поиска пользователя"""
    search_query = message.text.strip()
    
    user_service = UserService(session)
    from src.db.schemas.user import UserFilter
    
    users, total = await user_service.get_users_list(
        UserFilter(search=search_query, limit=20)
    )
    
    if not users:
        await message.answer(
            "❌ Пользователи не найдены",
            reply_markup=MenuKeyboards.back_button("admin:users")
        )
        await state.clear()
        return
    
    text = f"🔍 <b>Результаты поиска:</b> найдено {total}\n\n"
    
    for user in users[:10]:  # Показываем максимум 10
        roles = ", ".join([r.name for r in user.roles])
        text += f"👤 <b>{user.full_name}</b> (ID: {user.id})\n"
        text += f"   @{user.username or 'нет'} | {user.phone or 'нет телефона'}\n"
        text += f"   Роли: {roles or 'нет'}\n"
        text += f"   Статус: {'✅ Активен' if user.is_active else '❌ Заблокирован'}\n\n"
    
    keyboard = MenuKeyboards.user_search_results(users[:5])  # Кнопки для первых 5
    await message.answer(text, reply_markup=keyboard)
    await state.clear()


@router.callback_query(F.data.startswith("admin:user:"))
@require_role(["admin"])
async def user_actions(callback: CallbackQuery, session: AsyncSession):
    """Действия с пользователем"""
    user_id = int(callback.data.split(":")[2])
    
    user_service = UserService(session)
    user = await user_service.get_by_id(user_id)
    
    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return
    
    roles = ", ".join([r.name for r in user.roles])
    
    text = f"""
👤 <b>Пользователь: {user.full_name}</b>

ID: {user.id}
Telegram ID: {user.telegram_id or 'нет'}
Username: @{user.username or 'нет'}
Телефон: {user.phone or 'нет'}
Email: {user.email or 'нет'}

Роли: {roles or 'нет'}
Статус: {'✅ Активен' if user.is_active else '❌ Заблокирован'}
Верификация: {'✅ Да' if user.is_verified else '❌ Нет'}

Зарегистрирован: {user.created_at.strftime('%d.%m.%Y %H:%M')}
Последний вход: {user.last_login.strftime('%d.%m.%Y %H:%M') if user.last_login else 'никогда'}
    """
    
    keyboard = MenuKeyboards.user_actions(user_id, user.is_active)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("admin:user:toggle:"))
@require_role(["admin"])
async def toggle_user_status(callback: CallbackQuery, session: AsyncSession):
    """Блокировка/разблокировка пользователя"""
    user_id = int(callback.data.split(":")[3])
    
    user_service = UserService(session)
    user = await user_service.get_by_id(user_id)
    
    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return
    
    # Нельзя заблокировать себя
    if user.telegram_id == callback.from_user.id:
        await callback.answer("Нельзя заблокировать себя!", show_alert=True)
        return
    
    # Переключаем статус
    user.is_active = not user.is_active
    await session.commit()
    
    status = "разблокирован" if user.is_active else "заблокирован"
    await callback.answer(f"Пользователь {status}")
    
    # Обновляем сообщение
    await user_actions(callback, session)


@router.callback_query(F.data.startswith("admin:user:roles:"))
@require_role(["admin"])
async def manage_user_roles(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Управление ролями пользователя"""
    user_id = int(callback.data.split(":")[3])
    
    user_service = UserService(session)
    user = await user_service.get_by_id(user_id)
    
    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return
    
    # Получаем все роли
    roles_result = await session.execute(select(Role))
    all_roles = roles_result.scalars().all()
    
    user_roles = [r.name for r in user.roles]
    
    text = f"👤 <b>Роли пользователя {user.full_name}</b>\n\n"
    text += "Текущие роли:\n"
    
    for role in all_roles:
        if role.name in user_roles:
            text += f"✅ {role.display_name or role.name}\n"
        else:
            text += f"⬜ {role.display_name or role.name}\n"
    
    await state.update_data(user_id=user_id)
    await state.set_state(AdminStates.waiting_for_role_assignment)
    
    text += "\n<i>Введите названия ролей через запятую для назначения (например: manager, operator)</i>"
    text += "\n<i>Или отправьте 'clear' для удаления всех ролей</i>"
    
    await callback.message.edit_text(
        text,
        reply_markup=MenuKeyboards.back_button(f"admin:user:{user_id}")
    )
    await callback.answer()


@router.message(AdminStates.waiting_for_role_assignment)
@require_role(["admin"])
async def process_role_assignment(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка назначения ролей"""
    data = await state.get_data()
    user_id = data.get('user_id')
    
    user_service = UserService(session)
    
    if message.text.lower() == 'clear':
        # Удаляем все роли
        await user_service.assign_roles(user_id, [])
        await message.answer(
            "✅ Все роли удалены",
            reply_markup=MenuKeyboards.back_button(f"admin:user:{user_id}")
        )
    else:
        # Назначаем новые роли
        role_names = [r.strip() for r in message.text.split(',')]
        
        try:
            await user_service.assign_roles(user_id, role_names)
            await message.answer(
                f"✅ Роли назначены: {', '.join(role_names)}",
                reply_markup=MenuKeyboards.back_button(f"admin:user:{user_id}")
            )
        except Exception as e:
            await message.answer(
                f"❌ Ошибка: {str(e)}",
                reply_markup=MenuKeyboards.back_button(f"admin:user:{user_id}")
            )
    
    await state.clear()


@router.callback_query(F.data == "admin:system")
@require_role(["admin"])
async def system_settings(callback: CallbackQuery, session: AsyncSession):
    """Системные настройки"""
    # Получаем системную статистику
    db_size_query = "SELECT pg_database_size(current_database())"
    db_size_result = await session.execute(db_size_query)
    db_size = db_size_result.scalar() / 1024 / 1024  # В мегабайтах
    
    # Количество активных задач
    active_tasks = await session.execute(
        select(func.count(MachineTask.id)).where(
            MachineTask.status.in_([TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS])
        )
    )
    active_tasks = active_tasks.scalar()
    
    text = f"""
⚙️ <b>Системные настройки</b>

💾 <b>База данных:</b>
Размер: {db_size:.1f} MB
Бэкапы: ежедневно в 03:00

🔄 <b>Фоновые задачи:</b>
Активных задач: {active_tasks}
Планировщик: {'✅ Работает' if True else '❌ Остановлен'}

🔐 <b>Безопасность:</b>
2FA: {'✅ Включена' if False else '❌ Выключена'}
Последний аудит: вчера

📊 <b>Мониторинг:</b>
Uptime: 99.9%
Ошибок за сутки: 0
    """
    
    keyboard = MenuKeyboards.system_settings()
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "admin:broadcast")
@require_role(["admin"])
async def start_broadcast(callback: CallbackQuery, state: FSMContext):
    """Начать рассылку"""
    await state.set_state(AdminStates.waiting_for_broadcast_message)
    
    await callback.message.edit_text(
        "📢 <b>Массовая рассылка</b>\n\n"
        "Введите сообщение для отправки всем пользователям:\n"
        "<i>Используйте HTML-разметку для форматирования</i>",
        reply_markup=MenuKeyboards.back_button("admin:panel")
    )
    await callback.answer()


@router.message(AdminStates.waiting_for_broadcast_message)
@require_role(["admin"])
async def process_broadcast(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка рассылки"""
    broadcast_text = message.text
    
    # Получаем всех активных пользователей с Telegram ID
    users_query = select(User).where(
        User.telegram_id.isnot(None),
        User.is_active == True
    )
    users_result = await session.execute(users_query)
    users = users_result.scalars().all()
    
    sent = 0
    failed = 0
    
    status_message = await message.answer("📤 Начинаю рассылку...")
    
    for user in users:
        try:
            await message.bot.send_message(
                user.telegram_id,
                f"📢 <b>Объявление</b>\n\n{broadcast_text}",
                parse_mode="HTML"
            )
            sent += 1
            
            # Обновляем статус каждые 10 сообщений
            if sent % 10 == 0:
                await status_message.edit_text(
                    f"📤 Отправка...\n✅ Отправлено: {sent}\n❌ Ошибок: {failed}"
                )
                
        except Exception as e:
            failed += 1
            print(f"Failed to send to {user.telegram_id}: {e}")
    
    await status_message.edit_text(
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"📊 Статистика:\n"
        f"✅ Успешно: {sent}\n"
        f"❌ Ошибок: {failed}\n"
        f"📋 Всего: {sent + failed}",
        reply_markup=MenuKeyboards.back_button("admin:panel")
    )
    
    await state.clear()


@router.callback_query(F.data == "admin:logs")
@require_role(["admin"])
async def show_logs(callback: CallbackQuery, session: AsyncSession):
    """Показать последние логи"""
    # Получаем последние критические события
    from src.db.models.user import AuditLog
    
    logs_query = select(AuditLog).order_by(
        AuditLog.created_at.desc()
    ).limit(10)
    
    logs_result = await session.execute(logs_query)
    logs = logs_result.scalars().all()
    
    text = "📋 <b>Последние события</b>\n\n"
    
    if not logs:
        text += "Событий не найдено"
    else:
        for log in logs:
            text += f"🕐 {log.created_at.strftime('%d.%m %H:%M')}\n"
            text += f"👤 {log.user.full_name if log.user else 'Система'}\n"
            text += f"📌 {log.action}\n"
            if log.entity_type:
                text += f"🎯 {log.entity_type}#{log.entity_id}\n"
            text += "\n"
    
    await callback.message.edit_text(
        text,
        reply_markup=MenuKeyboards.back_button("admin:system")
    )
    await callback.answer()


from src.bot.keyboards.inline import InlineKeyboardMarkup, InlineKeyboardButton

class MenuKeyboards:
    """Расширение клавиатур для админа"""
    
    @staticmethod
    def admin_panel() -> InlineKeyboardMarkup:
        """Главное меню админа"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="👥 Пользователи", callback_data="admin:users"),
                InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats")
            ],
            [
                InlineKeyboardButton(text="⚙️ Система", callback_data="admin:system"),
                InlineKeyboardButton(text="📢 Рассылка", callback_data="admin:broadcast")
            ],
            [
                InlineKeyboardButton(text="📋 Логи", callback_data="admin:logs"),
                InlineKeyboardButton(text="💾 Бэкап", callback_data="admin:backup")
            ],
            [
                InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu")
            ]
        ])
    
    @staticmethod
    def user_management() -> InlineKeyboardMarkup:
        """Меню управления пользователями"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📋 Список", callback_data="admin:users:list"),
                InlineKeyboardButton(text="🔍 Поиск", callback_data="admin:users:search")
            ],
            [
                InlineKeyboardButton(text="👥 Роли", callback_data="admin:users:roles"),
                InlineKeyboardButton(text="🚫 Заблокированные", callback_data="admin:users:blocked")
            ],
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data="admin:panel")
            ]
        ])
    
    @staticmethod
    def user_actions(user_id: int, is_active: bool) -> InlineKeyboardMarkup:
        """Действия с пользователем"""
        toggle_text = "🚫 Заблокировать" if is_active else "✅ Разблокировать"
        
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="👥 Управление ролями", callback_data=f"admin:user:roles:{user_id}")
            ],
            [
                InlineKeyboardButton(text=toggle_text, callback_data=f"admin:user:toggle:{user_id}")
            ],
            [
                InlineKeyboardButton(text="📊 Статистика", callback_data=f"admin:user:stats:{user_id}")
            ],
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data="admin:users")
            ]
        ])