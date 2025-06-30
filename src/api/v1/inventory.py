from typing import List, Optional
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from src.db.database import get_async_session
from src.db.models.user import User
from src.db.models.inventory import LocationType, IngredientCategory, IngredientUnit
from src.services.inventory import InventoryService
from src.api.dependencies import (
    get_current_active_user, RequirePermission,
    PaginationParams
)
from src.core.exceptions import (
    IngredientNotFound, InsufficientStock
)

router = APIRouter()

# === Pydantic схемы ===

class IngredientBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=255)
    category: IngredientCategory
    unit: IngredientUnit
    cost_per_unit: Optional[Decimal] = Field(None, ge=0)
    min_stock_level: Optional[Decimal] = Field(None, ge=0)
    barcode: Optional[str] = None


class IngredientCreate(IngredientBase):
    pass


class IngredientResponse(IngredientBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class InventoryItemResponse(BaseModel):
    ingredient_id: int
    ingredient_name: str
    ingredient_code: str
    quantity: float
    unit: str
    batch_number: Optional[str]
    expiry_date: Optional[date]
    last_updated: datetime
    location_type: str
    location_id: int


class InventoryMovementCreate(BaseModel):
    ingredient_id: int
    quantity: Decimal = Field(..., gt=0)
    operation: str = Field(..., regex="^(issue|receive|transfer)$")
    from_location_type: Optional[LocationType] = None
    from_location_id: Optional[int] = None
    to_location_type: Optional[LocationType] = None
    to_location_id: Optional[int] = None
    batch_number: Optional[str] = None
    expiry_date: Optional[date] = None
    notes: Optional[str] = None


class InventorySummaryResponse(BaseModel):
    total_items: int
    total_value: float
    by_category: dict
    critical_items: List[dict]


class WeighingRecordCreate(BaseModel):
    ingredient_code: str
    weight: Decimal = Field(..., gt=0)
    machine_id: Optional[int] = None
    batch_number: Optional[str] = None


# === API Endpoints ===

@router.get("/ingredients", response_model=List[IngredientResponse])
async def get_ingredients(
    category: Optional[IngredientCategory] = None,
    search: Optional[str] = None,
    only_critical: bool = False,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(RequirePermission("inventory", "view"))
):
    """
    Получение списка ингредиентов.
    
    Требуется разрешение: inventory:view
    """
    service = InventoryService(session)
    ingredients = await service.get_ingredients_list(
        category=category,
        search=search,
        only_critical=only_critical
    )
    return ingredients


@router.post("/ingredients", response_model=IngredientResponse)
async def create_ingredient(
    ingredient_data: IngredientCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(RequirePermission("inventory", "edit"))
):
    """
    Создание нового ингредиента.
    
    Требуется разрешение: inventory:edit
    """
    service = InventoryService(session)
    ingredient = await service.create_ingredient(
        code=ingredient_data.code,
        name=ingredient_data.name,
        category=ingredient_data.category,
        unit=ingredient_data.unit,
        cost_per_unit=ingredient_data.cost_per_unit,
        min_stock_level=ingredient_data.min_stock_level,
        barcode=ingredient_data.barcode
    )
    return ingredient


@router.get("/stock/{location_type}/{location_id}", response_model=List[InventoryItemResponse])
async def get_location_stock(
    location_type: LocationType,
    location_id: int,
    ingredient_id: Optional[int] = None,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(RequirePermission("inventory", "view"))
):
    """
    Получение текущих остатков для локации.
    
    Требуется разрешение: inventory:view
    """
    service = InventoryService(session)
    stock = await service.get_current_stock(
        location_type=location_type,
        location_id=location_id,
        ingredient_id=ingredient_id
    )
    return stock


@router.get("/warehouse/summary", response_model=InventorySummaryResponse)
async def get_warehouse_summary(
    warehouse_id: int = 1,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(RequirePermission("inventory", "view"))
):
    """
    Получение сводки по складу.
    
    Требуется разрешение: inventory:view
    """
    service = InventoryService(session)
    summary = await service.get_inventory_summary()
    return summary


@router.post("/movements")
async def create_inventory_movement(
    movement: InventoryMovementCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(RequirePermission("inventory", "edit"))
):
    """
    Создание движения товара (выдача, приемка, перемещение).
    
    Требуется разрешение: inventory:edit
    """
    service = InventoryService(session)
    
    try:
        if movement.operation == "issue":
            result = await service.issue_from_warehouse(
                ingredient_id=movement.ingredient_id,
                quantity=movement.quantity,
                issued_by=current_user.id,
                notes=movement.notes
            )
            return {"message": "Товар успешно выдан", "record_id": result.id}
            
        elif movement.operation == "receive":
            result = await service.receive_to_warehouse(
                ingredient_id=movement.ingredient_id,
                quantity=movement.quantity,
                batch_number=movement.batch_number,
                expiry_date=movement.expiry_date,
                received_by=current_user.id,
                notes=movement.notes
            )
            return {"message": "Товар успешно принят", "record_id": result.id}
            
        elif movement.operation == "transfer":
            if not all([movement.from_location_type, movement.from_location_id,
                        movement.to_location_type, movement.to_location_id]):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Для перемещения требуется указать обе локации"
                )
            
            from_record, to_record = await service.transfer_inventory(
                ingredient_id=movement.ingredient_id,
                from_location_type=movement.from_location_type,
                from_location_id=movement.from_location_id,
                to_location_type=movement.to_location_type,
                to_location_id=movement.to_location_id,
                quantity=movement.quantity,
                transferred_by_id=current_user.id,
                notes=movement.notes
            )
            return {
                "message": "Товар успешно перемещен",
                "from_record_id": from_record.id,
                "to_record_id": to_record.id
            }
            
    except InsufficientStock as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except IngredientNotFound as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post("/weighing")
async def record_weighing(
    weighing_data: WeighingRecordCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(RequirePermission("inventory", "edit"))
):
    """
    Запись взвешивания (для операторов).
    
    Требуется разрешение: inventory:edit
    """
    service = InventoryService(session)
    
    # Получаем ингредиент по коду
    ingredient = await service.get_ingredient_by_code(weighing_data.ingredient_code)
    if not ingredient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ингредиент с кодом {weighing_data.ingredient_code} не найден"
        )
    
    result = await service.record_weighing(
        ingredient_id=ingredient.id,
        weight=weighing_data.weight,
        operator_id=current_user.id,
        machine_id=weighing_data.machine_id,
        batch_number=weighing_data.batch_number
    )
    
    return {
        "message": "Взвешивание записано",
        "data": result
    }


@router.get("/weighing/history")
async def get_weighing_history(
    limit: int = Query(10, ge=1, le=100),
    operator_id: Optional[int] = None,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(RequirePermission("inventory", "view"))
):
    """
    История взвешиваний.
    
    Требуется разрешение: inventory:view
    """
    service = InventoryService(session)
    
    # Если не админ/менеджер, показываем только свои взвешивания
    if not current_user.has_any_role(["admin", "manager"]):
        operator_id = current_user.id
    
    history = await service.get_recent_weighings(
        limit=limit,
        operator_id=operator_id
    )
    
    return {"items": history, "total": len(history)}


@router.get("/expiring")
async def get_expiring_items(
    days_ahead: int = Query(7, ge=1, le=30),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(RequirePermission("inventory", "view"))
):
    """
    Получение товаров с истекающим сроком годности.
    
    Требуется разрешение: inventory:view
    """
    service = InventoryService(session)
    expiring_items = await service.check_expiring_items(days_ahead)
    
    return {
        "days_ahead": days_ahead,
        "items": expiring_items,
        "total": len(expiring_items)
    }


@router.get("/movements")
async def get_inventory_movements(
    location_type: Optional[LocationType] = None,
    location_id: Optional[int] = None,
    ingredient_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(RequirePermission("inventory", "view"))
):
    """
    История движений товаров.
    
    Требуется разрешение: inventory:view
    """
    service = InventoryService(session)
    
    movements = await service.get_inventory_movements(
        location_type=location_type,
        location_id=location_id,
        ingredient_id=ingredient_id,
        date_from=date_from,
        date_to=date_to,
        limit=pagination.limit
    )
    
    return {
        "items": [
            {
                "id": m.id,
                "ingredient": {
                    "id": m.ingredient.id,
                    "name": m.ingredient.name,
                    "code": m.ingredient.code
                },
                "location_type": m.location_type.value,
                "location_id": m.location_id,
                "quantity": float(m.quantity),
                "batch_number": m.batch_number,
                "expiry_date": m.expiry_date,
                "action_timestamp": m.action_timestamp,
                "created_by": {
                    "id": m.created_by.id,
                    "name": m.created_by.full_name
                } if m.created_by else None,
                "notes": m.notes
            }
            for m in movements
        ],
        "total": len(movements),
        "limit": pagination.limit,
        "offset": pagination.skip
    }


# === Специальные endpoints для ролей ===

@router.get("/warehouse/critical", dependencies=[Depends(RequirePermission("inventory", "view"))])
async def get_critical_stock_for_warehouse(
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user)
):
    """
    Критические остатки для склада.
    Доступно: warehouse, manager, admin
    """
    if not current_user.has_any_role(["warehouse", "manager", "admin"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав"
        )
    
    service = InventoryService(session)
    summary = await service.get_inventory_summary()
    
    return {
        "critical_items": summary["critical_items"],
        "total_critical": len(summary["critical_items"])
    }


@router.post("/operator/return", dependencies=[Depends(RequirePermission("inventory", "edit"))])
async def operator_return_items(
    items: List[Dict[str, Any]] = Body(...),
    task_id: Optional[int] = None,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user)
):
    """
    Возврат товаров оператором после выполнения задачи.
    Доступно: operator, manager, admin
    """
    if not current_user.has_any_role(["operator", "manager", "admin"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав"
        )
    
    service = InventoryService(session)
    results = []
    
    for item in items:
        try:
            # Перемещаем из сумки обратно на склад
            if task_id:
                from_location_type = LocationType.BAG
                from_location_id = task_id
            else:
                # Если задача не указана, считаем что возврат напрямую
                from_location_type = LocationType.TRANSIT
                from_location_id = current_user.id
            
            _, to_record = await service.transfer_inventory(
                ingredient_id=item["ingredient_id"],
                from_location_type=from_location_type,
                from_location_id=from_location_id,
                to_location_type=LocationType.WAREHOUSE,
                to_location_id=1,  # Основной склад
                quantity=Decimal(str(item["quantity"])),
                transferred_by_id=current_user.id,
                notes=f"Возврат от оператора. {item.get('notes', '')}"
            )
            
            results.append({
                "ingredient_id": item["ingredient_id"],
                "quantity": item["quantity"],
                "status": "success",
                "record_id": to_record.id
            })
            
        except Exception as e:
            results.append({
                "ingredient_id": item["ingredient_id"],
                "quantity": item["quantity"],
                "status": "error",
                "error": str(e)
            })
    
    return {
        "message": "Обработка возвратов завершена",
        "results": results,
        "success_count": len([r for r in results if r["status"] == "success"]),
        "error_count": len([r for r in results if r["status"] == "error"])
    }