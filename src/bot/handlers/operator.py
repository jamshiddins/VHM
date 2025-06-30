# src/bot/handlers/operator.py

from typing import Optional
from datetime import datetime, timezone
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ContentType
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from ...services import (
    TaskService, RouteService, BagService, 
    CashCollectionService, VehicleService
)
from ...db.database import get_db
from ...db.schemas import (
    TaskPhotoCreate, TaskProblemCreate,
    CashDenominationCreate, VehicleLogCreate
)
from ..keyboards import operator as kb
from ..utils import require_role, photo_handler
from ...utils.storage import StorageService

router = Router()


class OperatorStates(StatesGroup):
    # Задачи
    viewing_tasks = State()
    performing_task = State()
    reporting_problem = State()
    
    # Инкассация
    cash_collection_start = State()
    cash_collection_denominations = State()
    cash_collection_complete = State()
    
    # Сумки
    checking_bag = State()
    bag_verification = State()
    
    # Транспорт
    vehicle_mileage = State()
    vehicle_fuel = State()
    
    # Ввод задним числом
    historical_entry = State()
    historical_date = State()


@router.message(Command("operator"))
@require_role("operator")
async def operator_menu(message: Message, state: FSMContext):
    """Главное меню оператора"""
    await state.clear()
    await message.answer(
        "👷 Меню оператора\n\n"
        "Выберите действие:",
        reply_markup=kb.operator_main_menu()
    )


# === ЗАДАЧИ И МАРШРУТЫ ===

@router.callback_query(F.data == "op_my_tasks")
@require_role("operator")
async def show_my_tasks(
    callback: CallbackQuery, 
    state: FSMContext,
    session: AsyncSession
):
    """Показать задачи оператора"""
    await callback.answer()
    await state.set_state(OperatorStates.viewing_tasks)
    
    service = RouteService()
    routes = await service.get_operator_routes(
        db=session,
        operator_id=callback.from_user.id,
        status='assigned'
    )
    
    if not routes:
        await callback.message.edit_text(
            "📋 У вас нет активных задач",
            reply_markup=kb.back_to_operator_menu()
        )
        return
    
    # Показываем маршруты
    text = "📋 <b>Ваши маршруты:</b>\n\n"
    for route in routes:
        text += f"🚛 Маршрут #{route.id} на {route.date.strftime('%d.%m.%Y')}\n"
        text += f"Задач: {len(route.tasks)}\n"
        text += f"Расстояние: {route.total_distance:.1f} км\n\n"
    
    await callback.message.edit_text(
        text,
        reply_markup=kb.routes_list(routes),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("route_"))
@require_role("operator")
async def show_route_details(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
):
    """Детали маршрута"""
    route_id = int(callback.data.split("_")[1])
    
    service = RouteService()
    progress = await service.get_route_progress(session, route_id)
    
    text = f"🚛 <b>Маршрут #{route_id}</b>\n\n"
    text += f"Статус: {progress['status']}\n"
    text += f"Прогресс: {progress['completed_tasks']}/{progress['total_tasks']} "
    text += f"({progress['completion_percentage']:.0f}%)\n\n"
    
    text += "<b>Задачи:</b>\n"
    for task in progress['tasks']:
        status_icon = "✅" if task['status'] == 'completed' else "⏳"
        text += f"{status_icon} {task['order']}. {task['machine']['name']}\n"
        text += f"   📍 {task['machine']['location']}\n"
    
    await callback.message.edit_text(
        text,
        reply_markup=kb.route_actions(route_id, progress['status']),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("start_route_"))
@require_role("operator")
async def start_route(
    callback: CallbackQuery,
    session: AsyncSession
):
    """Начать выполнение маршрута"""
    route_id = int(callback.data.split("_")[2])
    
    service = RouteService()
    route = await service.start_route(
        db=session,
        route_id=route_id,
        operator_id=callback.from_user.id
    )
    
    await callback.answer("✅ Маршрут начат!")
    await show_route_details(callback, None, session)


# === ПРОВЕРКА СУМКИ ===

@router.callback_query(F.data.startswith("check_bag_"))
@require_role("operator")
async def start_bag_check(
    callback: CallbackQuery,
    state: FSMContext
):
    """Начать проверку сумки"""
    task_id = int(callback.data.split("_")[2])
    
    await state.update_data(task_id=task_id)
    await state.set_state(OperatorStates.checking_bag)
    
    await callback.message.answer(
        "📦 <b>Проверка сумки-комплекта</b>\n\n"
        "Сфотографируйте содержимое сумки для проверки",
        parse_mode="HTML"
    )


@router.message(
    OperatorStates.checking_bag,
    F.content_type == ContentType.PHOTO
)
@require_role("operator")
async def receive_bag_photo(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    storage: StorageService
):
    """Получение фото сумки"""
    data = await state.get_data()
    task_id = data['task_id']
    
    # Сохранение фото
    photo_url = await photo_handler.save_photo(
        message.photo[-1],
        folder=f"bags/{task_id}/check",
        storage=storage
    )
    
    await state.update_data(bag_photo=photo_url)
    await state.set_state(OperatorStates.bag_verification)
    
    await message.answer(
        "Все элементы сумки на месте?",
        reply_markup=kb.bag_verification_menu()
    )


@router.callback_query(
    F.data.in_(["bag_complete", "bag_incomplete"]),
    OperatorStates.bag_verification
)
@require_role("operator")
async def verify_bag_contents(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
):
    """Подтверждение комплектности сумки"""
    data = await state.get_data()
    is_complete = callback.data == "bag_complete"
    
    # Получаем сумку для задачи
    task_service = TaskService()
    task = await task_service.get(session, data['task_id'])
    
    if not task or not task.bag_id:
        await callback.answer("❌ Сумка не найдена", show_alert=True)
        return
    
    # Проверка сумки
    bag_service = BagService()
    bag = await bag_service.verify_bag_by_operator(
        db=session,
        bag_id=task.bag_id,
        operator_id=callback.from_user.id,
        photo_url=data['bag_photo'],
        is_complete=is_complete,
        missing_items=[]  # TODO: добавить выбор недостающих элементов
    )
    
    await callback.answer("✅ Проверка завершена!")
    await state.clear()
    
    if is_complete:
        text = "✅ Сумка проверена, все элементы на месте"
    else:
        text = "⚠️ Сумка проверена, есть недостающие элементы"
    
    await callback.message.answer(
        text,
        reply_markup=kb.back_to_operator_menu()
    )


# === ИНКАССАЦИЯ ===

@router.callback_query(F.data == "op_cash_collection")
@require_role("operator")
async def start_cash_collection_menu(
    callback: CallbackQuery,
    state: FSMContext
):
    """Меню инкассации"""
    await callback.answer()
    await callback.message.edit_text(
        "💰 <b>Инкассация</b>\n\n"
        "Выберите автомат для инкассации:",
        reply_markup=kb.select_machine_for_collection(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("collect_machine_"))
@require_role("operator")
async def select_machine_for_collection(
    callback: CallbackQuery,
    state: FSMContext
):
    """Выбор автомата для инкассации"""
    machine_id = int(callback.data.split("_")[2])
    
    await state.update_data(machine_id=machine_id)
    await state.set_state(OperatorStates.cash_collection_start)
    
    await callback.message.answer(
        "📸 Сфотографируйте кассету ДО изъятия денег",
        reply_markup=kb.cancel_button()
    )


@router.message(
    OperatorStates.cash_collection_start,
    F.content_type == ContentType.PHOTO
)
@require_role("operator")
async def receive_before_photo(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    storage: StorageService
):
    """Получение фото до инкассации"""
    data = await state.get_data()
    
    # Сохранение фото
    photo_url = await photo_handler.save_photo(
        message.photo[-1],
        folder=f"cash_collection/{data['machine_id']}/before",
        storage=storage
    )
    
    # Начало инкассации
    service = CashCollectionService()
    collection = await service.start_collection(
        db=session,
        machine_id=data['machine_id'],
        operator_id=message.from_user.id,
        before_photo_url=photo_url
    )
    
    await state.update_data(collection_id=collection.id)
    await state.set_state(OperatorStates.cash_collection_denominations)
    
    await message.answer(
        "💵 <b>Подсчет купюр</b>\n\n"
        "Введите количество купюр по номиналам:\n\n"
        "Формат: номинал количество\n"
        "Например: 5000 10\n\n"
        "Когда закончите, нажмите 'Готово'",
        reply_markup=kb.cash_denominations_menu(),
        parse_mode="HTML"
    )
    
    await state.update_data(denominations=[])


@router.message(
    OperatorStates.cash_collection_denominations,
    F.text.regexp(r"^\d+\s+\d+$")
)
@require_role("operator")
async def add_denomination(
    message: Message,
    state: FSMContext
):
    """Добавление номинала"""
    parts = message.text.split()
    denomination = int(parts[0])
    quantity = int(parts[1])
    
    data = await state.get_data()
    denominations = data.get('denominations', [])
    
    # Проверка существующего номинала
    found = False
    for d in denominations:
        if d['denomination'] == denomination:
            d['quantity'] += quantity
            found = True
            break
    
    if not found:
        denominations.append({
            'denomination': denomination,
            'quantity': quantity
        })
    
    await state.update_data(denominations=denominations)
    
    # Показываем текущую сумму
    total = sum(d['denomination'] * d['quantity'] for d in denominations)
    
    text = f"✅ Добавлено: {denomination} x {quantity}\n\n"
    text += f"💰 Общая сумма: {total:,} сум\n\n"
    text += "Продолжайте вводить купюры или нажмите 'Готово'"
    
    await message.answer(text, reply_markup=kb.cash_denominations_menu())


@router.callback_query(
    F.data == "cash_done",
    OperatorStates.cash_collection_denominations
)
@require_role("operator")
async def save_denominations(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
):
    """Сохранение купюр"""
    data = await state.get_data()
    denominations = data.get('denominations', [])
    
    if not denominations:
        await callback.answer("❌ Введите хотя бы одну купюру", show_alert=True)
        return
    
    # Сохранение номиналов
    service = CashCollectionService()
    collection = await service.add_denominations(
        db=session,
        collection_id=data['collection_id'],
        denominations=[
            CashDenominationCreate(**d) for d in denominations
        ],
        operator_id=callback.from_user.id
    )
    
    await state.set_state(OperatorStates.cash_collection_complete)
    
    total = sum(d['denomination'] * d['quantity'] for d in denominations)
    
    await callback.message.answer(
        f"💰 Собрано: {total:,} сум\n\n"
        "📸 Теперь сфотографируйте кассету ПОСЛЕ изъятия денег",
        reply_markup=kb.cancel_button()
    )


@router.message(
    OperatorStates.cash_collection_complete,
    F.content_type == ContentType.PHOTO
)
@require_role("operator")
async def receive_after_photo(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    storage: StorageService
):
    """Получение фото после инкассации"""
    data = await state.get_data()
    
    # Сохранение фото
    photo_url = await photo_handler.save_photo(
        message.photo[-1],
        folder=f"cash_collection/{data['collection_id']}/after",
        storage=storage
    )
    
    # Завершение инкассации
    service = CashCollectionService()
    collection = await service.complete_collection(
        db=session,
        collection_id=data['collection_id'],
        operator_id=message.from_user.id,
        after_photo_url=photo_url,
        notes=None
    )
    
    await state.clear()
    
    text = "✅ <b>Инкассация завершена!</b>\n\n"
    text += f"💰 Собрано: {collection.amount_collected:,} сум\n"
    if collection.expected_amount:
        text += f"📊 Ожидалось: {collection.expected_amount:,} сум\n"
        if collection.discrepancy:
            text += f"⚠️ Расхождение: {collection.discrepancy:,} сум\n"
    
    await message.answer(
        text,
        reply_markup=kb.back_to_operator_menu(),
        parse_mode="HTML"
    )


# === ЖУРНАЛ ТРАНСПОРТА ===

@router.callback_query(F.data == "op_vehicle_log")
@require_role("operator")
async def vehicle_log_menu(
    callback: CallbackQuery,
    state: FSMContext
):
    """Меню журнала транспорта"""
    await callback.answer()
    await callback.message.edit_text(
        "🚗 <b>Журнал транспорта</b>\n\n"
        "Выберите действие:",
        reply_markup=kb.vehicle_log_menu(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "vehicle_mileage")
@require_role("operator")
async def start_mileage_entry(
    callback: CallbackQuery,
    state: FSMContext
):
    """Начать ввод пробега"""
    await state.set_state(OperatorStates.vehicle_mileage)
    await state.update_data(step="odometer")
    
    await callback.message.answer(
        "📏 <b>Ввод пробега</b>\n\n"
        "Введите текущие показания одометра (км):",
        parse_mode="HTML"
    )


@router.message(
    OperatorStates.vehicle_mileage,
    F.text.regexp(r"^\d+$")
)
@require_role("operator")
async def receive_odometer_reading(
    message: Message,
    state: FSMContext
):
    """Получение показаний одометра"""
    odometer = int(message.text)
    await state.update_data(odometer_reading=odometer)
    
    await message.answer(
        "📸 Сфотографируйте показания одометра"
    )


@router.message(
    OperatorStates.vehicle_mileage,
    F.content_type == ContentType.PHOTO
)
@require_role("operator")
async def receive_odometer_photo(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    storage: StorageService
):
    """Получение фото одометра"""
    data = await state.get_data()
    
    # Сохранение фото
    photo_url = await photo_handler.save_photo(
        message.photo[-1],
        folder="vehicles/odometer",
        storage=storage
    )
    
    # Сохранение записи о пробеге
    service = VehicleService()
    log = await service.add_mileage_log(
        db=session,
        vehicle_id=1,  # TODO: выбор автомобиля
        log_data=VehicleLogCreate(
            odometer_reading=data['odometer_reading'],
            log_date=datetime.now(timezone.utc)
        ),
        driver_id=message.from_user.id,
        odometer_photo=photo_url
    )
    
    await state.clear()
    
    text = "✅ <b>Пробег записан!</b>\n\n"
    text += f"📏 Показания: {log.odometer_reading:,} км\n"
    if log.mileage:
        text += f"🚗 Пробег за период: {log.mileage} км\n"
    
    await message.answer(
        text,
        reply_markup=kb.back_to_operator_menu(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "vehicle_fuel")
@require_role("operator")
async def start_fuel_entry(
    callback: CallbackQuery,
    state: FSMContext
):
    """Начать ввод заправки"""
    await state.set_state(OperatorStates.vehicle_fuel)
    await state.update_data(step="liters")
    
    await callback.message.answer(
        "⛽ <b>Заправка</b>\n\n"
        "Введите количество литров:",
        parse_mode="HTML"
    )


@router.message(
    OperatorStates.vehicle_fuel,
    F.text.regexp(r"^\d+\.?\d*$")
)
@require_role("operator")
async def receive_fuel_data(
    message: Message,
    state: FSMContext
):
    """Получение данных о заправке"""
    data = await state.get_data()
    step = data.get('step')
    
    if step == "liters":
        liters = float(message.text)
        await state.update_data(fuel_amount=liters, step="cost")
        await message.answer("💵 Введите стоимость заправки (сум):")
        
    elif step == "cost":
        cost = float(message.text)
        await state.update_data(fuel_cost=cost, step="station")
        await message.answer("⛽ Введите название АЗС:")
        
    elif step == "station":
        station = message.text
        await state.update_data(fuel_station=station, step="photo")
        await message.answer("📸 Сфотографируйте чек с заправки:")


@router.message(
    OperatorStates.vehicle_fuel,
    F.content_type == ContentType.PHOTO
)
@require_role("operator")
async def receive_fuel_receipt(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    storage: StorageService
):
    """Получение фото чека"""
    data = await state.get_data()
    
    # Сохранение фото
    photo_url = await photo_handler.save_photo(
        message.photo[-1],
        folder="vehicles/receipts",
        storage=storage
    )
    
    # Сохранение записи о заправке
    service = VehicleService()
    log = await service.add_fuel_log(
        db=session,
        vehicle_id=1,  # TODO: выбор автомобиля
        log_data=VehicleLogCreate(
            fuel_amount=data['fuel_amount'],
            fuel_cost=data['fuel_cost'],
            fuel_station=data['fuel_station'],
            log_date=datetime.now(timezone.utc)
        ),
        driver_id=message.from_user.id,
        receipt_photo=photo_url
    )
    
    await state.clear()
    
    text = "✅ <b>Заправка записана!</b>\n\n"
    text += f"⛽ Литров: {log.fuel_amount}\n"
    text += f"💵 Стоимость: {log.fuel_cost:,} сум\n"
    text += f"💰 Цена за литр: {log.fuel_price_per_liter:,.0f} сум\n"
    text += f"📍 АЗС: {log.fuel_station}\n"
    
    await message.answer(
        text,
        reply_markup=kb.back_to_operator_menu(),
        parse_mode="HTML"
    )


# === ВВОД ЗАДНИМ ЧИСЛОМ ===

@router.callback_query(F.data == "op_historical")
@require_role("operator")
async def historical_entry_menu(
    callback: CallbackQuery,
    state: FSMContext
):
    """Меню ввода задним числом"""
    await callback.answer()
    await callback.message.edit_text(
        "📅 <b>Ввод задним числом</b>\n\n"
        "Выберите тип операции:",
        reply_markup=kb.historical_entry_menu(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("hist_"))
@require_role("operator")
async def select_historical_type(
    callback: CallbackQuery,
    state: FSMContext
):
    """Выбор типа исторической операции"""
    operation_type = callback.data.replace("hist_", "")
    
    await state.update_data(historical_type=operation_type)
    await state.set_state(OperatorStates.historical_date)
    
    await callback.message.answer(
        "📅 Введите дату операции в формате ДД.ММ.ГГГГ\n"
        "Например: 25.03.2024"
    )


@router.message(
    OperatorStates.historical_date,
    F.text.regexp(r"^\d{2}\.\d{2}\.\d{4}$")
)
@require_role("operator")
async def receive_historical_date(
    message: Message,
    state: FSMContext
):
    """Получение исторической даты"""
    try:
        date_parts = message.text.split('.')
        historical_date = datetime(
            year=int(date_parts[2]),
            month=int(date_parts[1]),
            day=int(date_parts[0]),
            tzinfo=timezone.utc
        )
        
        # Проверка что дата в прошлом
        if historical_date > datetime.now(timezone.utc):
            await message.answer(
                "❌ Дата не может быть в будущем!",
                reply_markup=kb.cancel_button()
            )
            return
        
        await state.update_data(historical_date=historical_date)
        
        data = await state.get_data()
        operation_type = data['historical_type']
        
        # Перенаправление на соответствующий обработчик
        if operation_type == "task":
            await message.answer(
                "📋 Теперь введите данные по задаче за эту дату..."
            )
            # TODO: реализовать ввод исторической задачи
            
        elif operation_type == "collection":
            await message.answer(
                "💰 Начнем ввод данных инкассации за эту дату..."
            )
            # Переход к обычному процессу инкассации с historical_date
            await state.set_state(OperatorStates.cash_collection_start)
            
        elif operation_type == "mileage":
            await message.answer(
                "🚗 Введите показания одометра на эту дату..."
            )
            await state.set_state(OperatorStates.vehicle_mileage)
            
    except ValueError:
        await message.answer(
            "❌ Неверный формат даты! Используйте ДД.ММ.ГГГГ",
            reply_markup=kb.cancel_button()
        )


# === ПРОБЛЕМЫ ===

@router.callback_query(F.data.startswith("report_problem_"))
@require_role("operator")
async def start_problem_report(
    callback: CallbackQuery,
    state: FSMContext
):
    """Начать отчет о проблеме"""
    task_id = int(callback.data.split("_")[2])
    
    await state.update_data(task_id=task_id)
    await state.set_state(OperatorStates.reporting_problem)
    
    await callback.message.answer(
        "⚠️ <b>Сообщение о проблеме</b>\n\n"
        "Выберите тип проблемы:",
        reply_markup=kb.problem_types(),
        parse_mode="HTML"
    )


@router.callback_query(
    F.data.startswith("problem_type_"),
    OperatorStates.reporting_problem
)
@require_role("operator")
async def select_problem_type(
    callback: CallbackQuery,
    state: FSMContext
):
    """Выбор типа проблемы"""
    problem_type = callback.data.replace("problem_type_", "")
    
    await state.update_data(problem_type=problem_type)
    
    await callback.message.answer(
        "📝 Опишите проблему подробнее:"
    )


@router.message(
    OperatorStates.reporting_problem,
    F.text
)
@require_role("operator")
async def receive_problem_description(
    message: Message,
    state: FSMContext,
    session: AsyncSession
):
    """Получение описания проблемы"""
    data = await state.get_data()
    
    # Сохранение проблемы
    service = TaskService()
    problem = await service.report_problem(
        db=session,
        task_id=data['task_id'],
        problem_data=TaskProblemCreate(
            problem_type=data['problem_type'],
            description=message.text,
            is_critical=data['problem_type'] in ['machine_broken', 'no_access']
        ),
        reported_by_id=message.from_user.id
    )
    
    await state.clear()
    
    await message.answer(
        "✅ Проблема зарегистрирована!\n"
        "Менеджер будет уведомлен.",
        reply_markup=kb.back_to_operator_menu()
    )


# === ОТМЕНА ===

@router.callback_query(F.data == "cancel")
async def cancel_operation(
    callback: CallbackQuery,
    state: FSMContext
):
    """Отмена текущей операции"""
    await state.clear()
    await callback.answer("❌ Операция отменена")
    await operator_menu(callback.message, state)