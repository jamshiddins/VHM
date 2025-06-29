from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, PhotoSize
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from src.bot.keyboards.inline import OperatorKeyboards, MenuKeyboards
from src.services.task import TaskService
from src.services.user import UserService
from src.core.permissions import require_role

router = Router()


class TaskStates(StatesGroup):
    """Состояния для работы с задачами"""
    waiting_for_photo = State()
    waiting_for_comment = State()
    waiting_for_problem_description = State()


@router.callback_query(F.data == "operator:tasks")
@require_role(["operator", "manager", "admin"])
async def show_operator_tasks(callback: CallbackQuery, session: AsyncSession):
    """Показать задачи оператора"""
    user_service = UserService(session)
    task_service = TaskService(session)
    
    user = await user_service.get_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return
    
    # Получаем активные задачи оператора
    tasks = await task_service.get_user_active_tasks(user.id)
    
    if not tasks:
        text = "📋 <b>Мои задачи</b>\n\n😊 У вас пока нет активных задач."
        await callback.message.edit_text(
            text,
            reply_markup=MenuKeyboards.back_button("main_menu")
        )
    else:
        # Форматируем список задач
        tasks_data = []
        for task in tasks:
            task_info = {
                "id": task.id,
                "machine_name": f"{task.machine.code} - {task.machine.name}",
                "type": task.type.value,
                "completed": task.status == "completed"
            }
            tasks_data.append(task_info)
        
        text = f"📋 <b>Мои задачи</b>\n\nВсего задач: {len(tasks)}"
        await callback.message.edit_text(
            text,
            reply_markup=OperatorKeyboards.task_list(tasks_data)
        )
    
    await callback.answer()


@router.callback_query(F.data.startswith("task:"))
async def handle_task_action(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Обработка действий с задачей"""
    action_parts = callback.data.split(":")
    
    if len(action_parts) < 2:
        await callback.answer("Неверный формат данных", show_alert=True)
        return
    
    if action_parts[1] == "photo_before" and len(action_parts) == 3:
        # Запрос фото "до"
        task_id = int(action_parts[2])
        await state.update_data(task_id=task_id, photo_type="before")
        await state.set_state(TaskStates.waiting_for_photo)
        
        await callback.message.answer(
            "📸 Отправьте фото автомата ДО обслуживания.\n"
            "Используйте /cancel для отмены."
        )
        await callback.answer()
        
    elif action_parts[1] == "photo_after" and len(action_parts) == 3:
        # Запрос фото "после"
        task_id = int(action_parts[2])
        await state.update_data(task_id=task_id, photo_type="after")
        await state.set_state(TaskStates.waiting_for_photo)
        
        await callback.message.answer(
            "📸 Отправьте фото автомата ПОСЛЕ обслуживания.\n"
            "Используйте /cancel для отмены."
        )
        await callback.answer()
        
    elif action_parts[1] == "comment" and len(action_parts) == 3:
        # Запрос комментария
        task_id = int(action_parts[2])
        await state.update_data(task_id=task_id)
        await state.set_state(TaskStates.waiting_for_comment)
        
        await callback.message.answer(
            "💬 Напишите комментарий к задаче.\n"
            "Используйте /cancel для отмены."
        )
        await callback.answer()
        
    elif action_parts[1] == "problem" and len(action_parts) == 3:
        # Сообщение о проблеме
        task_id = int(action_parts[2])
        await state.update_data(task_id=task_id)
        await state.set_state(TaskStates.waiting_for_problem_description)
        
        await callback.message.answer(
            "⚠️ Опишите обнаруженную проблему.\n"
            "Укажите все важные детали.\n"
            "Используйте /cancel для отмены."
        )
        await callback.answer()
        
    elif action_parts[1] == "complete" and len(action_parts) == 3:
        # Завершение задачи
        task_id = int(action_parts[2])
        task_service = TaskService(session)
        
        try:
            await task_service.complete_task(task_id)
            await callback.message.edit_text(
                "✅ Задача успешно завершена!",
                reply_markup=MenuKeyboards.back_button("operator:tasks")
            )
        except Exception as e:
            await callback.answer(f"Ошибка: {str(e)}", show_alert=True)
            
    elif len(action_parts) == 2 and action_parts[1].isdigit():
        # Просмотр деталей задачи
        task_id = int(action_parts[1])
        task_service = TaskService(session)
        
        task = await task_service.get_task_details(task_id)
        if not task:
            await callback.answer("Задача не найдена", show_alert=True)
            return
        
        # Форматируем информацию о задаче
        status_emoji = {
            "pending": "⏳",
            "assigned": "👤",
            "in_progress": "🔄",
            "completed": "✅",
            "cancelled": "❌",
            "failed": "⚠️"
        }.get(task.status.value, "❓")
        
        task_text = f"""
{status_emoji} <b>Задача #{task.id}</b>

<b>Тип:</b> {task.type.value}
<b>Автомат:</b> {task.machine.code} - {task.machine.name}
<b>Адрес:</b> {task.machine.location_address or 'Не указан'}
<b>Статус:</b> {task.status.value}

<b>Описание:</b>
{task.description or 'Нет описания'}

<b>Создана:</b> {task.created_at.strftime('%d.%m.%Y %H:%M')}
"""
        
        if task.items:
            task_text += "\n<b>Необходимые ингредиенты:</b>\n"
            for item in task.items:
                task_text += f"• {item.ingredient.name}: {item.planned_quantity} {item.ingredient.unit}\n"
        
        await callback.message.edit_text(
            task_text,
            reply_markup=OperatorKeyboards.task_actions(
                task_id,
                completed=task.status.value == "completed"
            )
        )
        await callback.answer()


@router.message(TaskStates.waiting_for_photo)
async def process_task_photo(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка фото от оператора"""
    if not message.photo:
        await message.answer("❌ Пожалуйста, отправьте фото.")
        return
    
    data = await state.get_data()
    task_id = data.get("task_id")
    photo_type = data.get("photo_type")
    
    # Берем фото наилучшего качества
    photo: PhotoSize = message.photo[-1]
    
    task_service = TaskService(session)
    
    try:
        # Сохраняем фото
        await task_service.add_task_photo(
            task_id=task_id,
            photo_type=photo_type,
            telegram_file_id=photo.file_id,
            caption=message.caption
        )
        
        await message.answer(
            f"✅ Фото '{photo_type}' сохранено!",
            reply_markup=OperatorKeyboards.task_actions(task_id)
        )
        await state.clear()
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при сохранении фото: {str(e)}")


@router.message(TaskStates.waiting_for_comment)
async def process_task_comment(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка комментария к задаче"""
    if not message.text:
        await message.answer("❌ Пожалуйста, отправьте текстовый комментарий.")
        return
    
    data = await state.get_data()
    task_id = data.get("task_id")
    
    task_service = TaskService(session)
    
    try:
        # Добавляем комментарий к задаче
        await task_service.add_task_comment(task_id, message.text)
        
        await message.answer(
            "✅ Комментарий добавлен!",
            reply_markup=OperatorKeyboards.task_actions(task_id)
        )
        await state.clear()
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при сохранении комментария: {str(e)}")


@router.message(TaskStates.waiting_for_problem_description)
async def process_problem_description(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка описания проблемы"""
    if not message.text:
        await message.answer("❌ Пожалуйста, опишите проблему текстом.")
        return
    
    data = await state.get_data()
    task_id = data.get("task_id")
    
    task_service = TaskService(session)
    
    try:
        # Добавляем проблему к задаче
        await task_service.report_problem(
            task_id=task_id,
            problem_type="other",  # TODO: Добавить выбор типа проблемы
            description=message.text,
            is_critical=False  # TODO: Добавить определение критичности
        )
        
        await message.answer(
            "⚠️ Проблема зарегистрирована!\n"
            "Менеджер будет уведомлен.",
            reply_markup=OperatorKeyboards.task_actions(task_id)
        )
        await state.clear()
        
        # TODO: Отправить уведомление менеджеру
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при сохранении проблемы: {str(e)}")


@router.callback_query(F.data == "operator:routes")
@require_role(["operator", "manager", "admin"])
async def show_operator_routes(callback: CallbackQuery, session: AsyncSession):
    """Показать маршруты оператора"""
    # TODO: Реализовать показ маршрутов
    await callback.message.edit_text(
        "🗺 <b>Мои маршруты</b>\n\n"
        "<i>Функционал в разработке...</i>",
        reply_markup=MenuKeyboards.back_button("main_menu")
    )
    await callback.answer()


@router.callback_query(F.data == "operator:report")
@require_role(["operator", "manager", "admin"])
async def create_operator_report(callback: CallbackQuery, session: AsyncSession):
    """Создать отчет оператора"""
    # TODO: Реализовать создание отчета
    await callback.message.edit_text(
        "📸 <b>Создание отчета</b>\n\n"
        "<i>Функционал в разработке...</i>",
        reply_markup=MenuKeyboards.back_button("main_menu")
    )
    await callback.answer()