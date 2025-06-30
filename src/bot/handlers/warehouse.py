# src/bot/handlers/warehouse.py

from typing import Optional, List
from datetime import datetime, timezone
from decimal import Decimal
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ContentType
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from ...services import (
    InventoryService, BunkerService, BagService,
    SupplierService
)
from ...db.database import get_db
from ...db.schemas import (
    InventoryMovementCreate, BunkerWeighingCreate,
    BagItemCreate
)
from ..keyboards import warehouse as kb
from ..utils import require_role, photo_handler
from ...utils.storage import StorageService

router = Router()


class WarehouseStates(StatesGroup):
    # Приемка товара
    receiving_select_supplier = State()
    receiving_select_ingredient = State()
    receiving_weighing = State()
    receiving_photo = State()
    
    # Взвешивание бункеров
    bunker_select = State()
    bunker_ingredient = State()
    bunker_weighing = State()
    bunker_photo = State()
    
    # Сборка сумок
    bag_creation = State()
    bag_adding_items = State()
    bag_item_type = State()
    bag_item_details = State()
    
    # Выдача/возврат
    issue_select_operator = State()
    issue_confirm = State()
    return_process = State()
    
    # Инвентаризация
    inventory_location = State()
    inventory_counting = State()


@router.message(Command("warehouse"))
@require_role("warehouse")
async def warehouse_menu(message: Message, state: FSMContext):
    """Главное меню склада"""
    await state.clear()
    await message.answer(
        "📦 Меню склада\n\n"
        "Выберите действие:",
        reply_markup=kb.warehouse_main_menu()
    )


# === ОСТАТКИ ===

@router.callback_query(F.data == "wh_stock")
@require_role("warehouse")
async def show_stock_summary(
    callback: CallbackQuery,
    session: AsyncSession
):
    """Показать остатки на складе"""
    await callback.answer()
    
    service = InventoryService()
    summary = await service.get_warehouse_summary(session)
    
    text = "📦 <b>Остатки на складе:</b>\n\n"
    
    for category, ingredients in summary.items():
        text += f"<b>{category}:</b>\n"
        for ing in ingredients:
            text += f"• {ing['name']}: {ing['quantity']:.1f} {ing['unit']}\n"
        text += "\n"
    
    # Критические остатки
    critical = await service.get_critical_stock(session)
    if critical:
        text += "⚠️ <b>Критические остатки:</b>\n"
        for item in critical:
            text += f"• {item['name']}: {item['quantity']:.1f} {item['unit']} "
            text += f"(мин: {item['min_quantity']})\n"
    
    await callback.message.edit_text(
        text,
        reply_markup=kb.stock_actions_menu(),
        parse_mode="HTML"
    )


# === ПРИЕМКА ТОВАРА ===

@router.callback_query(F.data == "wh_receive")
@require_role("warehouse")
async def start_receiving(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
):
    """Начать приемку товара"""
    await callback.answer()
    await state.set_state(WarehouseStates.receiving_select_supplier)
    
    # Получаем список поставщиков
    service = SupplierService()
    suppliers = await service.get_list(
        db=session,
        filters={'is_active': True}
    )
    
    if not suppliers:
        await callback.message.edit_text(
            "❌ Нет активных поставщиков",
            reply_markup=kb.back_to_warehouse_menu()
        )
        return
    
    await callback.message.edit_text(
        "🚚 <b>Приемка товара</b>\n\n"
        "Выберите поставщика:",
        reply_markup=kb.suppliers_list(suppliers),
        parse_mode="HTML"
    )


@router.callback_query(
    F.data.startswith("supplier_"),
    WarehouseStates.receiving_select_supplier
)
@require_role("warehouse")
async def select_supplier(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
):
    """Выбор поставщика"""
    supplier_id = int(callback.data.split("_")[1])
    await state.update_data(supplier_id=supplier_id)
    await state.set_state(WarehouseStates.receiving_select_ingredient)
    
    # Получаем ингредиенты поставщика
    # TODO: загрузить ингредиенты поставщика
    
    await callback.message.edit_text(
        "📦 Выберите ингредиент для приемки:",
        reply_markup=kb.ingredients_list([]),  # TODO: передать ингредиенты
        parse_mode="HTML"
    )


@router.callback_query(
    F.data.startswith("ingredient_"),
    WarehouseStates.receiving_select_ingredient
)
@require_role("warehouse")
async def select_ingredient(
    callback: CallbackQuery,
    state: FSMContext
):
    """Выбор ингредиента"""
    ingredient_id = int(callback.data.split("_")[1])
    await state.update_data(ingredient_id=ingredient_id)
    await state.set_state(WarehouseStates.receiving_weighing)
    
    await callback.message.answer(
        "⚖️ Введите вес/количество товара:"
    )


@router.message(
    WarehouseStates.receiving_weighing,
    F.text.regexp(r"^\d+\.?\d*$")
)
@require_role("warehouse")
async def receive_weight(
    message: Message,
    state: FSMContext
):
    """Получение веса"""
    weight = float(message.text)
    await state.update_data(quantity=weight)
    await state.set_state(WarehouseStates.receiving_photo)
    
    await message.answer(
        "📸 Сфотографируйте товар и накладную"
    )


@router.message(
    WarehouseStates.receiving_photo,
    F.content_type == ContentType.PHOTO
)
@require_role("warehouse")
async def receive_photo(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    storage: StorageService
):
    """Получение фото приемки"""
    data = await state.get_data()
    
    # Сохранение фото
    photo_url = await photo_handler.save_photo(
        message.photo[-1],
        folder="receiving",
        storage=storage
    )
    
    # Создание движения товара
    service = InventoryService()
    movement = await service.create_inventory_movement(
        db=session,
        movement_data=InventoryMovementCreate(
            ingredient_id=data['ingredient_id'],
            from_location_type=None,
            from_location_id=None,
            to_location_type='warehouse',
            to_location_id=1,  # Основной склад
            quantity=data['quantity'],
            reason='receiving',
            reference_type='purchase',
            reference_id=data.get('purchase_id')
        ),
        current_user_id=message.from_user.id,
        photo_url=photo_url
    )
    
    await state.clear()
    
    await message.answer(
        f"✅ Товар принят!\n"
        f"Количество: {data['quantity']} единиц",
        reply_markup=kb.back_to_warehouse_menu()
    )


# === ВЗВЕШИВАНИЕ БУНКЕРОВ ===

@router.callback_query(F.data == "wh_bunkers")
@require_role("warehouse")
async def bunkers_menu(
    callback: CallbackQuery,
    state: FSMContext
):
    """Меню работы с бункерами"""
    await callback.answer()
    await callback.message.edit_text(
        "🏺 <b>Работа с бункерами</b>\n\n"
        "Выберите действие:",
        reply_markup=kb.bunkers_menu(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "bunker_weigh")
@require_role("warehouse")
async def start_bunker_weighing(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
):
    """Начать взвешивание бункера"""
    await state.set_state(WarehouseStates.bunker_select)
    
    # Получаем пустые бункеры
    service = BunkerService()
    bunkers = await service.get_bunkers_by_status(
        db=session,
        status='empty'
    )
    
    if not bunkers:
        await callback.message.edit_text(
            "❌ Нет доступных пустых бункеров",
            reply_markup=kb.back_to_warehouse_menu()
        )
        return
    
    await callback.message.edit_text(
        "🏺 Выберите бункер для взвешивания:",
        reply_markup=kb.bunkers_list(bunkers),
        parse_mode="HTML"
    )


@router.callback_query(
    F.data.startswith("bunker_"),
    WarehouseStates.bunker_select
)
@require_role("warehouse")
async def select_bunker_for_weighing(
    callback: CallbackQuery,
    state: FSMContext
):
    """Выбор бункера"""
    bunker_id = int(callback.data.split("_")[1])
    await state.update_data(bunker_id=bunker_id)
    await state.set_state(WarehouseStates.bunker_ingredient)
    
    await callback.message.edit_text(
        "📦 Выберите ингредиент для заполнения:",
        reply_markup=kb.ingredients_list([]),  # TODO: загрузить ингредиенты
        parse_mode="HTML"
    )


@router.callback_query(
    F.data.startswith("ingredient_"),
    WarehouseStates.bunker_ingredient
)
@require_role("warehouse")
async def select_bunker_ingredient(
    callback: CallbackQuery,
    state: FSMContext
):
    """Выбор ингредиента для бункера"""
    ingredient_id = int(callback.data.split("_")[1])
    await state.update_data(ingredient_id=ingredient_id)
    await state.set_state(WarehouseStates.bunker_weighing)
    
    await callback.message.answer(
        "⚖️ Взвесьте бункер с продуктом и введите вес БРУТТО (кг):"
    )


@router.message(
    WarehouseStates.bunker_weighing,
    F.text.regexp(r"^\d+\.?\d*$")
)
@require_role("warehouse")
async def receive_bunker_weight(
    message: Message,
    state: FSMContext
):
    """Получение веса бункера"""
    gross_weight = float(message.text)
    await state.update_data(gross_weight=gross_weight)
    await state.set_state(WarehouseStates.bunker_photo)
    
    await message.answer(
        "📸 Сфотографируйте взвешенный бункер"
    )


@router.message(
    WarehouseStates.bunker_photo,
    F.content_type == ContentType.PHOTO
)
@require_role("warehouse")
async def receive_bunker_photo(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    storage: StorageService
):
    """Получение фото бункера"""
    data = await state.get_data()
    
    # Сохранение фото
    photo_url = await photo_handler.save_photo(
        message.photo[-1],
        folder=f"bunkers/{data['bunker_id']}/weighing",
        storage=storage
    )
    
    # Взвешивание бункера
    service = BunkerService()
    weighing = await service.weigh_bunker(
        db=session,
        bunker_id=data['bunker_id'],
        weighing_data=BunkerWeighingCreate(
            ingredient_id=data['ingredient_id'],
            gross_weight=data['gross_weight']
        ),
        current_user=message.from_user,
        photo_url=photo_url
    )
    
    await state.clear()
    
    text = "✅ <b>Бункер взвешен!</b>\n\n"
    text += f"⚖️ Вес брутто: {weighing.gross_weight:.1f} кг\n"
    text += f"📦 Вес нетто: {weighing.net_weight:.1f} кг\n"
    
    await message.answer(
        text,
        reply_markup=kb.back_to_warehouse_menu(),
        parse_mode="HTML"
    )


# === СБОРКА СУМОК ===

@router.callback_query(F.data == "wh_bags")
@require_role("warehouse")
async def bags_menu(
    callback: CallbackQuery,
    state: FSMContext
):
    """Меню работы с сумками"""
    await callback.answer()
    await callback.message.edit_text(
        "👜 <b>Работа с сумками</b>\n\n"
        "Выберите действие:",
        reply_markup=kb.bags_menu(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "bag_create")
@require_role("warehouse")
async def start_bag_creation(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
):
    """Начать сборку сумки"""
    # TODO: выбор задачи для сумки
    await state.set_state(WarehouseStates.bag_creation)
    
    await callback.message.edit_text(
        "👜 <b>Сборка сумки-комплекта</b>\n\n"
        "Выберите задачу для которой собирается сумка:",
        reply_markup=kb.tasks_list([]),  # TODO: загрузить задачи
        parse_mode="HTML"
    )


@router.callback_query(F.data == "bag_add_item")
@require_role("warehouse")
async def add_item_to_bag(
    callback: CallbackQuery,
    state: FSMContext
):
    """Добавить элемент в сумку"""
    await state.set_state(WarehouseStates.bag_item_type)
    
    await callback.message.answer(
        "Что добавляем в сумку?",
        reply_markup=kb.bag_item_types()
    )


@router.callback_query(
    F.data.in_(["item_bunker", "item_ingredient", "item_other"]),
    WarehouseStates.bag_item_type
)
@require_role("warehouse")
async def select_item_type(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
):
    """Выбор типа элемента"""
    item_type = callback.data.replace("item_", "")
    await state.update_data(item_type=item_type)
    await state.set_state(WarehouseStates.bag_item_details)
    
    if item_type == "bunker":
        # Показать заполненные бункеры
        service = BunkerService()
        bunkers = await service.get_bunkers_by_status(
            db=session,
            status='filled'
        )
        
        await callback.message.edit_text(
            "Выберите бункер:",
            reply_markup=kb.bunkers_list(bunkers)
        )
        
    elif item_type == "ingredient":
        await callback.message.edit_text(
            "Выберите ингредиент:",
            reply_markup=kb.ingredients_list([])  # TODO
        )
        
    else:
        await callback.message.answer(
            "Введите описание элемента:"
        )


# === ВЫДАЧА СУМОК ===

@router.callback_query(F.data == "bag_issue")
@require_role("warehouse")
async def start_bag_issue(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
):
    """Начать выдачу сумки"""
    await state.set_state(WarehouseStates.issue_select_operator)
    
    # TODO: получить операторов
    operators = []
    
    await callback.message.edit_text(
        "👷 Выберите оператора для выдачи:",
        reply_markup=kb.operators_list(operators),
        parse_mode="HTML"
    )


# === ВОЗВРАТ ===

@router.callback_query(F.data == "wh_returns")
@require_role("warehouse")
async def start_returns(
    callback: CallbackQuery,
    state: FSMContext
):
    """Начать прием возвратов"""
    await state.set_state(WarehouseStates.return_process)
    
    await callback.message.edit_text(
        "📥 <b>Прием возвратов</b>\n\n"
        "Сканируйте или введите код возвращаемого элемента:",
        parse_mode="HTML"
    )


# === ОТЧЕТЫ ===

@router.callback_query(F.data == "wh_reports")
@require_role("warehouse")
async def warehouse_reports_menu(
    callback: CallbackQuery
):
    """Меню отчетов склада"""
    await callback.answer()
    await callback.message.edit_text(
        "📊 <b>Отчеты склада</b>\n\n"
        "Выберите отчет:",
        reply_markup=kb.reports_menu(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "report_movements")
@require_role("warehouse")
async def show_movements_report(
    callback: CallbackQuery,
    session: AsyncSession
):
    """Отчет по движениям"""
    service = InventoryService()
    movements = await service.get_recent_movements(
        db=session,
        location_type='warehouse',
        limit=20
    )
    
    text = "📋 <b>Последние движения товара:</b>\n\n"
    
    for movement in movements:
        direction = "➡️" if movement.to_location_type == 'warehouse' else "⬅️"
        text += f"{direction} {movement.ingredient.name}: "
        text += f"{movement.quantity} {movement.ingredient.unit}\n"
        text += f"   {movement.created_at.strftime('%d.%m %H:%M')}\n"
        text += f"   {movement.reason}\n\n"
    
    await callback.message.edit_text(
        text,
        reply_markup=kb.back_to_warehouse_menu(),
        parse_mode="HTML"
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
    await warehouse_menu(callback.message, state)