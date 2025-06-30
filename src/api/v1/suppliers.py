# src/api/v1/suppliers.py

from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.database import get_db
from ...db.schemas import (
    SupplierCreate, SupplierUpdate, SupplierResponse,
    PurchaseCreate, PurchaseResponse, PurchaseItemCreate,
    SupplierIngredientCreate, MaintenanceScheduleCreate,
    MaintenanceScheduleResponse, MaintenanceHistoryCreate
)
from ...services import SupplierService, MaintenanceService
from ...core.auth import get_current_user
from ...core.permissions import require_permissions
from ...db.models import User

router = APIRouter(tags=["suppliers_maintenance"])


# Supplier endpoints

@router.get("/suppliers", response_model=List[SupplierResponse])
@require_permissions(["suppliers.view"])
async def get_suppliers(
    is_active: bool = Query(True),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить список поставщиков"""
    service = SupplierService()
    
    filters = {'is_active': is_active}
    if search:
        # Поиск по имени, ИНН, контактам
        filters['search'] = search
    
    suppliers = await service.get_list(
        db=db,
        skip=skip,
        limit=limit,
        filters=filters
    )
    return suppliers


@router.post("/suppliers", response_model=SupplierResponse)
@require_permissions(["suppliers.create"])
async def create_supplier(
    supplier_data: SupplierCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Создать нового поставщика"""
    service = SupplierService()
    supplier = await service.create_supplier(
        db=db,
        supplier_data=supplier_data,
        current_user=current_user
    )
    return supplier


@router.get("/suppliers/{supplier_id}", response_model=SupplierResponse)
@require_permissions(["suppliers.view"])
async def get_supplier(
    supplier_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить детали поставщика"""
    service = SupplierService()
    supplier = await service.get(db, supplier_id)
    
    if not supplier:
        raise HTTPException(status_code=404, detail="Поставщик не найден")
    
    return supplier


@router.patch("/suppliers/{supplier_id}", response_model=SupplierResponse)
@require_permissions(["suppliers.update"])
async def update_supplier(
    supplier_id: int,
    supplier_update: SupplierUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Обновить поставщика"""
    service = SupplierService()
    supplier = await service.update(
        db=db,
        id=supplier_id,
        obj_in=supplier_update
    )
    
    if not supplier:
        raise HTTPException(status_code=404, detail="Поставщик не найден")
    
    return supplier


@router.post("/suppliers/{supplier_id}/ingredients")
@require_permissions(["suppliers.manage_ingredients"])
async def add_supplier_ingredients(
    supplier_id: int,
    ingredients: List[SupplierIngredientCreate],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Добавить ингредиенты поставщика"""
    service = SupplierService()
    created = await service.add_supplier_ingredients(
        db=db,
        supplier_id=supplier_id,
        ingredients=ingredients
    )
    return {
        "message": f"Добавлено ингредиентов: {len(created)}",
        "ingredients": created
    }


@router.get("/suppliers/{supplier_id}/statistics")
@require_permissions(["suppliers.view_statistics"])
async def get_supplier_statistics(
    supplier_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Статистика по поставщику"""
    service = SupplierService()
    stats = await service.get_supplier_statistics(db, supplier_id)
    return stats


@router.get("/suppliers/best-for-ingredient/{ingredient_id}")
@require_permissions(["suppliers.view"])
async def find_best_supplier(
    ingredient_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Найти лучшего поставщика для ингредиента"""
    service = SupplierService()
    best = await service.find_best_supplier_for_ingredient(db, ingredient_id)
    
    if not best:
        raise HTTPException(
            status_code=404,
            detail="Поставщики для этого ингредиента не найдены"
        )
    
    return best


# Purchase endpoints

@router.get("/purchases", response_model=List[PurchaseResponse])
@require_permissions(["purchases.view"])
async def get_purchases(
    supplier_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить список закупок"""
    service = SupplierService()
    
    filters = {}
    if supplier_id:
        filters['supplier_id'] = supplier_id
    if status:
        filters['status'] = status
    
    purchases = await service.get_list(
        db=db,
        model_class="Purchase",
        skip=skip,
        limit=limit,
        filters=filters,
        date_from=date_from,
        date_to=date_to
    )
    return purchases


@router.post("/purchases", response_model=PurchaseResponse)
@require_permissions(["purchases.create"])
async def create_purchase(
    purchase_data: PurchaseCreate,
    items: List[PurchaseItemCreate],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Создать закупку"""
    service = SupplierService()
    purchase = await service.create_purchase(
        db=db,
        purchase_data=purchase_data,
        items=items,
        current_user=current_user
    )
    return purchase


@router.post("/purchases/{purchase_id}/confirm")
@require_permissions(["purchases.confirm"])
async def confirm_purchase(
    purchase_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Подтвердить закупку"""
    service = SupplierService()
    purchase = await service.confirm_purchase(
        db=db,
        purchase_id=purchase_id,
        current_user=current_user
    )
    return purchase


@router.post("/purchases/{purchase_id}/receive")
@require_permissions(["purchases.receive"])
async def receive_purchase(
    purchase_id: int,
    received_items: Dict[int, Dict[str, Any]],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Принять закупку на склад"""
    service = SupplierService()
    purchase = await service.receive_purchase(
        db=db,
        purchase_id=purchase_id,
        received_items=received_items,
        current_user=current_user
    )
    return purchase


@router.get("/purchases/calendar")
@require_permissions(["purchases.view"])
async def get_purchases_calendar(
    start_date: datetime,
    end_date: datetime,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Календарь закупок"""
    service = SupplierService()
    calendar = await service.get_purchases_calendar(
        db=db,
        start_date=start_date,
        end_date=end_date
    )
    return calendar


# Maintenance endpoints

@router.get("/maintenance/schedules", response_model=List[MaintenanceScheduleResponse])
@require_permissions(["maintenance.view"])
async def get_maintenance_schedules(
    machine_id: Optional[int] = Query(None),
    is_active: bool = Query(True),
    maintenance_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить графики ТО"""
    service = MaintenanceService()
    
    filters = {'is_active': is_active}
    if machine_id:
        filters['machine_id'] = machine_id
    if maintenance_type:
        filters['maintenance_type'] = maintenance_type
    
    schedules = await service.get_list(db=db, filters=filters)
    return schedules


@router.post("/maintenance/schedules", response_model=MaintenanceScheduleResponse)
@require_permissions(["maintenance.create"])
async def create_maintenance_schedule(
    schedule_data: MaintenanceScheduleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Создать график ТО"""
    service = MaintenanceService()
    schedule = await service.create_maintenance_schedule(
        db=db,
        schedule_data=schedule_data,
        current_user=current_user
    )
    return schedule


@router.get("/maintenance/overdue")
@require_permissions(["maintenance.view"])
async def get_overdue_maintenance(
    days_overdue: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить просроченные ТО"""
    service = MaintenanceService()
    schedules = await service.get_overdue_maintenance(
        db=db,
        days_overdue=days_overdue
    )
    return schedules


@router.get("/maintenance/upcoming")
@require_permissions(["maintenance.view"])
async def get_upcoming_maintenance(
    days_ahead: int = Query(7, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить предстоящие ТО"""
    service = MaintenanceService()
    schedules = await service.get_upcoming_maintenance(
        db=db,
        days_ahead=days_ahead
    )
    return schedules


@router.post("/maintenance/schedules/{schedule_id}/perform")
async def perform_maintenance(
    schedule_id: int,
    history_data: MaintenanceHistoryCreate,
    photos: Optional[List[str]] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Выполнить ТО"""
    service = MaintenanceService()
    history = await service.perform_maintenance(
        db=db,
        schedule_id=schedule_id,
        history_data=history_data,
        performed_by_id=current_user.id,
        photos=photos
    )
    return history


@router.post("/maintenance/create-tasks")
@require_permissions(["maintenance.create_tasks"])
async def create_maintenance_tasks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Создать задачи ТО для просроченных графиков"""
    service = MaintenanceService()
    tasks = await service.create_maintenance_tasks(db, current_user)
    return {
        "message": f"Создано задач ТО: {len(tasks)}",
        "tasks": tasks
    }


@router.get("/maintenance/history/{machine_id}")
@require_permissions(["maintenance.view_history"])
async def get_maintenance_history(
    machine_id: int,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """История ТО автомата"""
    service = MaintenanceService()
    history = await service.get_maintenance_history(
        db=db,
        machine_id=machine_id,
        limit=limit
    )
    return history


@router.get("/maintenance/statistics")
@require_permissions(["maintenance.view_statistics"])
async def get_maintenance_statistics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Статистика техобслуживания"""
    service = MaintenanceService()
    stats = await service.get_maintenance_statistics(db)
    return stats