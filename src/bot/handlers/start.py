from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from src.bot.keyboards.inline import MenuKeyboards
from src.services.user import UserService
from src.db.schemas.user import UserCreate

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession):
    """Обработчик команды /start"""
    user_service = UserService(session)
    
    # Проверяем, есть ли пользователь в БД
    user = await user_service.get_by_telegram_id(message.from_user.id)
    
    if not user:
        # Регистрация нового пользователя
        user_data = UserCreate(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            full_name=message.from_user.full_name,
            role_names=["operator"]  # По умолчанию оператор
        )
        
        try:
            user = await user_service.create_user(user_data)
            welcome_text = (
                f"👋 Добро пожаловать в VendHub, {message.from_user.first_name}!\n\n"
                "🎉 Вы успешно зарегистрированы в системе.\n"
                "📋 Вам назначена роль: <b>Оператор</b>\n\n"
                "Для получения других ролей обратитесь к администратору."
            )
        except Exception as e:
            await message.answer(
                "❌ Ошибка при регистрации. Обратитесь к администратору."
            )
            return
    else:
        # Приветствие существующего пользователя
        roles_text = ", ".join([role.display_name or role.name for role in user.roles])
        welcome_text = (
            f"👋 С возвращением, {user.full_name}!\n\n"
            f"👤 Ваши роли: <b>{roles_text}</b>\n"
            f"📱 Выберите действие из меню ниже:"
        )
    
    # Отправляем приветствие с главным меню
    user_roles = [role.name for role in user.roles]
    await message.answer(
        welcome_text,
        reply_markup=MenuKeyboards.main_menu(user_roles)
    )


@router.message(Command("menu"))
async def cmd_menu(message: Message, session: AsyncSession):
    """Показать главное меню"""
    user_service = UserService(session)
    user = await user_service.get_by_telegram_id(message.from_user.id)
    
    if not user:
        await message.answer(
            "❌ Вы не зарегистрированы в системе.\n"
            "Используйте /start для регистрации."
        )
        return
    
    user_roles = [role.name for role in user.roles]
    await message.answer(
        "📱 Главное меню:",
        reply_markup=MenuKeyboards.main_menu(user_roles)
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Помощь по боту"""
    help_text = """
❓ <b>Помощь по VendHub Bot</b>

<b>Основные команды:</b>
/start - Начать работу с ботом
/menu - Показать главное меню
/profile - Мой профиль
/tasks - Мои задачи (для операторов)
/stats - Статистика
/settings - Настройки
/help - Эта справка
/cancel - Отменить текущее действие

<b>Роли в системе:</b>
👷 <b>Оператор</b> - обслуживание автоматов
📦 <b>Склад</b> - управление запасами
💼 <b>Менеджер</b> - управление и отчеты
💎 <b>Инвестор</b> - просмотр инвестиций
⚙️ <b>Админ</b> - полный доступ

<b>Навигация:</b>
Используйте кнопки под сообщениями для навигации.
В любой момент можете вернуться в главное меню командой /menu

<b>Поддержка:</b>
По всем вопросам обращайтесь к администратору.
    """
    
    await message.answer(help_text)


@router.callback_query(F.data == "main_menu")
async def callback_main_menu(callback: CallbackQuery, session: AsyncSession):
    """Возврат в главное меню"""
    user_service = UserService(session)
    user = await user_service.get_by_telegram_id(callback.from_user.id)
    
    if not user:
        await callback.answer("Вы не зарегистрированы", show_alert=True)
        return
    
    user_roles = [role.name for role in user.roles]
    await callback.message.edit_text(
        "📱 Главное меню:",
        reply_markup=MenuKeyboards.main_menu(user_roles)
    )
    await callback.answer()


@router.callback_query(F.data == "profile")
async def callback_profile(callback: CallbackQuery, session: AsyncSession):
    """Показать профиль пользователя"""
    user_service = UserService(session)
    user = await user_service.get_user_with_stats(callback.from_user.id)
    
    if not user:
        await callback.answer("Вы не зарегистрированы", show_alert=True)
        return
    
    roles_text = ", ".join([role.display_name or role.name for role in user.roles])
    
    profile_text = f"""
👤 <b>Мой профиль</b>

<b>Имя:</b> {user.full_name}
<b>Username:</b> @{user.username or 'не указан'}
<b>Telegram ID:</b> <code>{user.telegram_id}</code>
<b>Телефон:</b> {user.phone or 'не указан'}
<b>Email:</b> {user.email or 'не указан'}

<b>Роли:</b> {roles_text}
<b>Статус:</b> {'✅ Активен' if user.is_active else '❌ Заблокирован'}
<b>Верификация:</b> {'✅ Подтвержден' if user.is_verified else '⏳ Не подтвержден'}

<b>📊 Статистика:</b>
🏪 Автоматов под управлением: {user.managed_machines_count}
📋 Активных задач: {user.active_tasks_count}
✅ Выполнено задач: {user.completed_tasks_count}
💰 Сумма инвестиций: {user.total_investment:,.0f} UZS

<b>Дата регистрации:</b> {user.created_at.strftime('%d.%m.%Y')}
    """
    
    await callback.message.edit_text(
        profile_text,
        reply_markup=MenuKeyboards.back_button("main_menu")
    )
    await callback.answer()


@router.callback_query(F.data == "stats")
async def callback_stats(callback: CallbackQuery, session: AsyncSession):
    """Показать общую статистику"""
    # TODO: Реализовать получение статистики
    stats_text = """
📊 <b>Общая статистика</b>

<b>Сегодня:</b>
💰 Продажи: 1,234,567 UZS
☕ Чашек кофе: 156
🍫 Снеков: 89
📈 Средний чек: 7,900 UZS

<b>Этот месяц:</b>
💰 Продажи: 45,678,900 UZS
📈 Рост к прошлому месяцу: +12.5%
🏆 Лучший автомат: VM-001

<b>Операционные показатели:</b>
✅ Работающих автоматов: 45/50
⚠️ Требуют обслуживания: 3
🔧 На ремонте: 2

<i>Обновлено: {datetime.now().strftime('%H:%M')}</i>
    """
    
    await callback.message.edit_text(
        stats_text,
        reply_markup=MenuKeyboards.back_button("main_menu")
    )
    await callback.answer()


@router.callback_query(F.data == "settings")
async def callback_settings(callback: CallbackQuery, session: AsyncSession):
    """Настройки пользователя"""
    # TODO: Реализовать настройки
    settings_text = """
⚙️ <b>Настройки</b>

🔔 <b>Уведомления:</b>
├ Новые задачи: ✅
├ Отчеты: ✅
└ Системные: ✅

🌐 <b>Язык:</b> 🇷🇺 Русский

🕐 <b>Часовой пояс:</b> UTC+5 (Ташкент)

📱 <b>Интерфейс:</b>
└ Компактный режим: ❌

<i>Функционал в разработке...</i>
    """
    
    await callback.message.edit_text(
        settings_text,
        reply_markup=MenuKeyboards.back_button("main_menu")
    )
    await callback.answer()


@router.callback_query(F.data == "help")
async def callback_help(callback: CallbackQuery):
    """Помощь через callback"""
    await callback_help_handler(callback)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Отмена текущего действия"""
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Нечего отменять.")
        return
    
    await state.clear()
    await message.answer(
        "❌ Действие отменено.",
        reply_markup=MenuKeyboards.back_button("main_menu")
    )


async def callback_help_handler(callback: CallbackQuery):
    """Вспомогательная функция для показа помощи"""
    help_text = """
❓ <b>Помощь по VendHub Bot</b>

<b>Основные команды:</b>
/start - Начать работу с ботом
/menu - Показать главное меню
/profile - Мой профиль
/tasks - Мои задачи (для операторов)
/stats - Статистика
/settings - Настройки
/help - Эта справка
/cancel - Отменить текущее действие

<b>Роли в системе:</b>
👷 <b>Оператор</b> - обслуживание автоматов
📦 <b>Склад</b> - управление запасами
💼 <b>Менеджер</b> - управление и отчеты
💎 <b>Инвестор</b> - просмотр инвестиций
⚙️ <b>Админ</b> - полный доступ

<b>Навигация:</b>
Используйте кнопки под сообщениями для навигации.
В любой момент можете вернуться в главное меню командой /menu

<b>Поддержка:</b>
По всем вопросам обращайтесь к администратору.
    """
    
    await callback.message.edit_text(
        help_text,
        reply_markup=MenuKeyboards.back_button("main_menu")
    )
    await callback.answer()