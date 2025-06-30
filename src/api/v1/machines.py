from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.database import get_async_session
from src.db.models.user import User
from src.db.models.machine import MachineType, MachineStatus
from src.services.machine import MachineService
from src.api.dependencies import (
    get_current_active_user, RequirePermission,
    PaginationParams, SortingParams
)
from src.core.exceptions import MachineNotFound, MachineAlreadyExists
from pydantic import BaseModel, Field
from datetime import date
from typing import Dict, Any


# === Pydantic схемы ===

class MachineBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=1, max_length=255)
    type: MachineType
    model: Optional[str] = None
    serial_number: Optional[str] = None
    location_address: Optional[str] = None
    location_lat: Optional[float] = Field(None, ge=-90, le=90)
    location_lng: Optional[float] = Field(None, ge=-180, le=180)


class MachineCreate(MachineBase):
    responsible_user_id: Optional[int] = None


class MachineUpdate(BaseModel):
    name: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    status: Optional[MachineStatus] = None
    location_address: Optional[str] = None
    location_lat: Optional[float] = Field(None, ge=-90, le=90)
    location_lng: Optional[float] = Field(None, ge=-180, le=180)
    responsible_user_id: Optional[int] = None
    settings: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class MachineResponse(MachineBase):
    id: int
    uuid: str
    status: MachineStatus
    installation_date: Optional[date]
    last_service_date: Optional[date]
    responsible_user: Optional[Dict[str, Any]] = None
    total_investment: float = 0
    investor_count: int = 0
    
    class Config:
        from_attributes = True


class MachineListResponse(BaseModel):
    items: List[MachineResponse]
    total: int
    limit: int
    offset: int


class MachineStatistics(BaseModel):
    machine_id: Optional[int] = None
    machine_code: Optional[str] = None
    status: Optional[str] = None
    sales_this_month: Optional[Dict[str, Any]] = None
    tasks: Optional[Dict[str, int]] = None
    total: Optional[int] = None
    by_status: Optional[Dict[str, int]] = None
    by_type: Optional[Dict[str, int]] = None
    operational_rate: Optional[float] = None
    total_investment: Optional[float] = None
    investor_count: Optional[int] = None


class MachineMapData(BaseModel):
    id: int
    code: str
    name: str
    type: str
    status: str
    lat: float
    lng: float
    address: Optional[str]
    is_operational: bool


# === API Router ===

router = APIRouter()


@router.post("/", response_model=MachineResponse)
async def create_machine(
    machine_data: MachineCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(RequirePermission("machines", "create"))
):
    """
    Создание нового автомата.
    
    Требуется разрешение: machines:create
    """
    service = MachineService(session)
    
    try:
        machine = await service.create_machine(
            code=machine_data.code,
            name=machine_data.name,
            machine_type=machine_data.type,
            model=machine_data.model,
            serial_number=machine_data.serial_number,
            location_address=machine_data.location_address,
            location_lat=machine_data.location_lat,
            location_lng=machine_data.location_lng,
            responsible_user_id=machine_data.responsible_user_id
        )
        
        # Форматируем ответ
        response = MachineResponse(
            **machine.__dict__,
            responsible_user={
                "id": machine.responsible_user.id,
                "name": machine.responsible_user.full_name
            } if machine.responsible_user else None,
            total_investment=machine.total_investment,
            investor_count=len([inv for inv in machine.investors if inv.is_active])
        )
        
        return response
        
    except MachineAlreadyExists as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )


@router.get("/", response_model=MachineListResponse)
async def get_machines(
    machine_type: Optional[MachineType] = None,
    status: Optional[MachineStatus] = None,
    responsible_user_id: Optional[int] = None,
    search: Optional[str] = None,
    has_issues: Optional[bool] = None,
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(RequirePermission("machines", "view"))
):
    """
    Получение списка автоматов с фильтрацией.
    
    Требуется разрешение: machines:view
    """
    service = MachineService(session)
    
    machines, total = await service.get_machines_list(
        machine_type=machine_type,
        status=status,
        responsible_user_id=responsible_user_id,
        search=search,
        has_issues=has_issues,
        limit=pagination.limit,
        offset=pagination.skip
    )
    
    # Форматируем ответ
    items = []
    for machine in machines:
        items.append(MachineResponse(
            **machine.__dict__,
            responsible_user={
                "id": machine.responsible_user.id,
                "name": machine.responsible_user.full_name
            } if machine.responsible_user else None,
            total_investment=0,  # TODO: Подсчитать
            investor_count=0     # TODO: Подсчитать
        ))
    
    return MachineListResponse(
        items=items,
        total=total,
        limit=pagination.limit,
        offset=pagination.skip
    )


@router.get("/map", response_model=List[MachineMapData])
async def get_machines_map(
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(RequirePermission("machines", "view"))
):
    """
    Получение данных автоматов для карты.
    
    Требуется разрешение: machines:view
    """
    service = MachineService(session)
    map_data = await service.get_machines_map_data()
    
    return [MachineMapData(**data) for data in map_data]


@router.get("/nearby", response_model=List[MachineResponse])
async def get_nearby_machines(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(5.0, gt=0, le=50),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(RequirePermission("machines", "view"))
):
    """
    Получение ближайших автоматов.
    
    Требуется разрешение: machines:view
    """
    service = MachineService(session)
    machines = await service.get_nearby_machines(lat, lng, radius_km)
    
    return [
        MachineResponse(
            **machine.__dict__,
            responsible_user={
                "id": machine.responsible_user.id,
                "name": machine.responsible_user.full_name
            } if machine.responsible_user else None
        )
        for machine in machines
    ]


@router.get("/statistics", response_model=MachineStatistics)
async def get_machines_statistics(
    machine_id: Optional[int] = None,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(RequirePermission("machines", "view"))
):
    """
    Получение статистики по автоматам.
    
    Требуется разрешение: machines:view
    """
    service = MachineService(session)
    
    try:
        stats = await service.get_machine_statistics(machine_id)
        return MachineStatistics(**stats)
    except MachineNotFound as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get("/{machine_id}", response_model=MachineResponse)
async def get_machine(
    machine_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(RequirePermission("machines", "view"))
):
    """
    Получение информации об автомате.
    
    Требуется разрешение: machines:view
    """
    service = MachineService(session)
    machine = await service.get_machine_by_id(machine_id)
    
    if not machine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Автомат с ID {machine_id} не найден"
        )
    
    return MachineResponse(
        **machine.__dict__,
        responsible_user={
            "id": machine.responsible_user.id,
            "name": machine.responsible_user.full_name
        } if machine.responsible_user else None,
        total_investment=machine.total_investment,
        investor_count=len([inv for inv in machine.investors if inv.is_active])
    )


@router.patch("/{machine_id}", response_model=MachineResponse)
async def update_machine(
    machine_id: int,
    update_data: MachineUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(RequirePermission("machines", "edit"))
):
    """
    Обновление данных автомата.
    
    Требуется разрешение: machines:edit
    """
    service = MachineService(session)
    
    try:
        machine = await service.update_machine(
            machine_id,
            update_data.dict(exclude_unset=True)
        )
        
        return MachineResponse(
            **machine.__dict__,
            responsible_user={
                "id": machine.responsible_user.id,
                "name": machine.responsible_user.full_name
            } if machine.responsible_user else None
        )
        
    except MachineNotFound as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.put("/{machine_id}/status", response_model=MachineResponse)
async def update_machine_status(
    machine_id: int,
    status: MachineStatus,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(RequirePermission("machines", "edit"))
):
    """
    Изменение статуса автомата.
    
    Требуется разрешение: machines:edit
    """
    service = MachineService(session)
    
    try:
        machine = await service.update_machine_status(machine_id, status)
        
        return MachineResponse(
            **machine.__dict__,
            responsible_user={
                "id": machine.responsible_user.id,
                "name": machine.responsible_user.full_name
            } if machine.responsible_user else None
        )
        
    except MachineNotFound as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.delete("/{machine_id}")
async def delete_machine(
    machine_id: int,
    permanent: bool = False,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(RequirePermission("machines", "delete"))
):
    """
    Удаление автомата.
    
    Требуется разрешение: machines:delete
    """
    service = MachineService(session)
    
    try:
        await service.delete_machine(machine_id, soft=not permanent)
        return {"message": "Автомат успешно удален"}
        
    except MachineNotFound as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )