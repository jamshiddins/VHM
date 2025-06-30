# src/api/v1/bunkers.py

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.database import get_db
from ...db.schemas import (
    BunkerCreate, BunkerUpdate, BunkerResponse,
    BunkerWeighingCreate, BunkerWeighingResponse,
    BagCreate, BagResponse, BagItemCreate
)
from ...services import BunkerService, BagService
from ...core.auth import get_current_user
from ...core.permissions import require_permissions
from ...db.models import User
from ...utils.storage import StorageService

router = APIRouter(tags=["bunkers_bags"])


# Bunker endpoints

@router.get("/bunkers", response_model=List[BunkerResponse])
@require_permissions(["bunkers.view"])
async def get_bunkers(
    status: Optional[str] = Query(None),
    ingredient_id: Optional[int] = Query(None),
    needs_cleaning: bool = Query(False),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить список бункеров"""
    service = BunkerService()
    
    if needs_cleaning:
        bunkers = await service.get_bunkers_for_cleaning(db)
    else:
        filters = {}
        if status:
            filters['status'] = status
        if ingredient_id:
            filters['current_ingredient_id'] = ingredient_id
            
        bunkers = await service.get_list(
            db=db,
            skip=skip,
            limit=limit,
            filters=filters
        )
    
    return bunkers


@router.post("/bunkers", response_model=BunkerResponse)
@require_permissions(["bunkers.create"])
async def create_bunker(
    bunker_data: BunkerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Создать новый бункер"""
    service = BunkerService()
    bunker = await service.create_bunker(
        db=db,
        bunker_data=bunker_data,
        current_user=current_user
    )
    return bunker


@router.get("/bunkers/{bunker_id}", response_model=BunkerResponse)
@require_permissions(["bunkers.view"])
async def get_bunker(
    bunker_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить детали бункера"""
    service = BunkerService()
    bunker = await service.get(db, bunker_id)
    
    if not bunker:
        raise HTTPException(status_code=404, detail="Бункер не найден")
    
    return bunker


@router.patch("/bunkers/{bunker_id}", response_model=BunkerResponse)
@require_permissions(["bunkers.update"])
async def update_bunker(
    bunker_id: int,
    bunker_update: BunkerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Обновить бункер"""
    service = BunkerService()
    bunker = await service.update(
        db=db,
        id=bunker_id,
        obj_in=bunker_update
    )
    
    if not bunker:
        raise HTTPException(status_code=404, detail="Бункер не найден")
    
    return bunker


@router.post("/bunkers/{bunker_id}/weigh", response_model=BunkerWeighingResponse)
@require_permissions(["bunkers.weigh"])
async def weigh_bunker(
    bunker_id: int,
    weighing_data: BunkerWeighingCreate,
    file: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    storage: StorageService = Depends()
):
    """Взвесить бункер"""
    photo_url = None
    if file:
        photo_url = await storage.upload_file(
            file=file,
            folder=f"bunkers/{bunker_id}/weighing"
        )
    
    service = BunkerService()
    weighing = await service.weigh_bunker(
        db=db,
        bunker_id=bunker_id,
        weighing_data=weighing_data,
        current_user=current_user,
        photo_url=photo_url
    )
    return weighing


@router.post("/bunkers/{bunker_id}/assign-to-bag")
@require_permissions(["bunkers.assign"])
async def assign_bunker_to_bag(
    bunker_id: int,
    bag_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Привязать бункер к сумке"""
    service = BunkerService()
    bag_item = await service.assign_to_bag(
        db=db,
        bunker_id=bunker_id,
        bag_id=bag_id,
        current_user=current_user
    )
    return {"message": "Бункер успешно привязан к сумке", "bag_item_id": bag_item.id}


@router.post("/bunkers/{bunker_id}/return")
@require_permissions(["bunkers.return"])
async def return_bunker(
    bunker_id: int,
    is_empty: bool,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Вернуть бункер от оператора"""
    service = BunkerService()
    bunker = await service.return_from_operator(
        db=db,
        bunker_id=bunker_id,
        operator_id=current_user.id,
        is_empty=is_empty,
        current_user=current_user
    )
    return bunker


@router.post("/bunkers/{bunker_id}/maintenance")
@require_permissions(["bunkers.maintenance"])
async def send_to_maintenance(
    bunker_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Отправить бункер на мойку"""
    service = BunkerService()
    bunker = await service.mark_for_cleaning(
        db=db,
        bunker_id=bunker_id,
        current_user=current_user
    )
    return bunker


@router.get("/bunkers/{bunker_id}/history")
@require_permissions(["bunkers.view_history"])
async def get_bunker_history(
    bunker_id: int,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """История операций с бункером"""
    service = BunkerService()
    history = await service.get_bunker_history(
        db=db,
        bunker_id=bunker_id,
        limit=limit
    )
    return history


@router.get("/bunkers/statistics/summary")
@require_permissions(["bunkers.view_statistics"])
async def get_bunker_statistics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Статистика по бункерам"""
    service = BunkerService()
    stats = await service.get_bunker_statistics(db)
    return stats


# Bag endpoints

@router.get("/bags", response_model=List[BagResponse])
@require_permissions(["bags.view"])
async def get_bags(
    status: Optional[str] = Query(None),
    task_id: Optional[int] = Query(None),
    operator_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить список сумок"""
    service = BagService()
    
    filters = {}
    if status:
        filters['status'] = status
    if task_id:
        filters['task_id'] = task_id
    
    # Операторы видят только свои сумки
    if 'operator' in [r.name for r in current_user.roles]:
        filters['issued_to_id'] = current_user.id
    elif operator_id:
        filters['issued_to_id'] = operator_id
    
    bags = await service.get_list(
        db=db,
        skip=skip,
        limit=limit,
        filters=filters
    )
    return bags


@router.post("/bags", response_model=BagResponse)
@require_permissions(["bags.create"])
async def create_bag(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Создать сумку для задачи"""
    service = BagService()
    bag = await service.create_bag_for_task(
        db=db,
        task_id=task_id,
        current_user=current_user
    )
    return bag


@router.get("/bags/{bag_id}", response_model=BagResponse)
@require_permissions(["bags.view"])
async def get_bag(
    bag_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить детали сумки"""
    service = BagService()
    bag = await service.get(db, bag_id)
    
    if not bag:
        raise HTTPException(status_code=404, detail="Сумка не найдена")
    
    # Проверка прав доступа
    if 'operator' in [r.name for r in current_user.roles] and \
       bag.issued_to_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа к этой сумке")
    
    return bag


@router.post("/bags/{bag_id}/items")
@require_permissions(["bags.add_items"])
async def add_items_to_bag(
    bag_id: int,
    items: List[BagItemCreate],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Добавить элементы в сумку"""
    service = BagService()
    created_items = await service.add_items_to_bag(
        db=db,
        bag_id=bag_id,
        items=items,
        current_user=current_user
    )
    return {"message": f"Добавлено элементов: {len(created_items)}", "items": created_items}


@router.post("/bags/{bag_id}/complete")
@require_permissions(["bags.complete"])
async def complete_bag_preparation(
    bag_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Завершить подготовку сумки"""
    service = BagService()
    bag = await service.complete_bag_preparation(
        db=db,
        bag_id=bag_id,
        current_user=current_user
    )
    return bag


@router.post("/bags/{bag_id}/issue")
@require_permissions(["bags.issue"])
async def issue_bag(
    bag_id: int,
    operator_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Выдать сумку оператору"""
    service = BagService()
    bag = await service.issue_bag_to_operator(
        db=db,
        bag_id=bag_id,
        operator_id=operator_id,
        current_user=current_user
    )
    return bag


@router.post("/bags/{bag_id}/verify")
async def verify_bag(
    bag_id: int,
    is_complete: bool,
    file: UploadFile = File(...),
    missing_items: Optional[List[int]] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    storage: StorageService = Depends()
):
    """Проверить сумку (оператор)"""
    # Загрузка фото
    photo_url = await storage.upload_file(
        file=file,
        folder=f"bags/{bag_id}/verification"
    )
    
    service = BagService()
    bag = await service.verify_bag_by_operator(
        db=db,
        bag_id=bag_id,
        operator_id=current_user.id,
        photo_url=photo_url,
        is_complete=is_complete,
        missing_items=missing_items
    )
    return bag


@router.post("/bags/{bag_id}/return")
async def return_bag(
    bag_id: int,
    notes: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Вернуть сумку на склад"""
    service = BagService()
    bag = await service.return_bag(
        db=db,
        bag_id=bag_id,
        operator_id=current_user.id,
        current_user=current_user,
        notes=notes
    )
    return bag


@router.get("/bags/{bag_id}/contents")
@require_permissions(["bags.view"])
async def get_bag_contents(
    bag_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить содержимое сумки"""
    service = BagService()
    contents = await service.get_bag_contents(db, bag_id)
    return contents


@router.get("/bags/operator/{operator_id}")
@require_permissions(["bags.view_operator"])
async def get_operator_bags(
    operator_id: int,
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить сумки оператора"""
    # Проверка прав
    if 'operator' in [r.name for r in current_user.roles] and \
       operator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа к сумкам другого оператора")
    
    service = BagService()
    bags = await service.get_operator_bags(
        db=db,
        operator_id=operator_id,
        status=status
    )
    return bags


@router.get("/bags/statistics/summary")
@require_permissions(["bags.view_statistics"])
async def get_bag_statistics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Статистика по сумкам"""
    service = BagService()
    stats = await service.get_bag_statistics(db)
    return stats