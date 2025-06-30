# src/api/v1/tasks.py

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.database import get_db
from ...db.schemas import (
    TaskCreate, TaskUpdate, TaskResponse, TaskWithDetails,
    TaskPhotoCreate, TaskProblemCreate, RouteCreate, RouteResponse
)
from ...services import TaskService, RouteService
from ...core.auth import get_current_user
from ...core.permissions import require_permissions
from ...db.models import User
from ...utils.storage import StorageService

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/", response_model=List[TaskResponse])
async def get_tasks(
    status: Optional[str] = Query(None),
    task_type: Optional[str] = Query(None),
    machine_id: Optional[int] = Query(None),
    assigned_to: Optional[int] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить список задач"""
    service = TaskService()
    
    # Фильтрация по правам
    if 'admin' not in [r.name for r in current_user.roles] and \
       'manager' not in [r.name for r in current_user.roles]:
        # Операторы видят только свои задачи
        assigned_to = current_user.id
    
    tasks = await service.get_tasks_filtered(
        db=db,
        status=status,
        task_type=task_type,
        machine_id=machine_id,
        assigned_to_id=assigned_to,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit
    )
    
    return tasks


@router.post("/", response_model=TaskResponse)
@require_permissions(["tasks.create"])
async def create_task(
    task_data: TaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Создать новую задачу"""
    service = TaskService()
    task = await service.create(
        db=db,
        obj_in=task_data,
        created_by_id=current_user.id
    )
    return task


@router.get("/{task_id}", response_model=TaskWithDetails)
async def get_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить детали задачи"""
    service = TaskService()
    task = await service.get_with_details(db, task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    # Проверка прав доступа
    if 'admin' not in [r.name for r in current_user.roles] and \
       'manager' not in [r.name for r in current_user.roles] and \
       task.assigned_to_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа к этой задаче")
    
    return task


@router.patch("/{task_id}", response_model=TaskResponse)
@require_permissions(["tasks.update"])
async def update_task(
    task_id: int,
    task_update: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Обновить задачу"""
    service = TaskService()
    task = await service.update(
        db=db,
        id=task_id,
        obj_in=task_update
    )
    
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    return task


@router.post("/{task_id}/assign")
@require_permissions(["tasks.assign"])
async def assign_task(
    task_id: int,
    operator_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Назначить задачу оператору"""
    service = TaskService()
    task = await service.assign_task(
        db=db,
        task_id=task_id,
        operator_id=operator_id,
        assigned_by=current_user
    )
    return task


@router.post("/{task_id}/start")
async def start_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Начать выполнение задачи"""
    service = TaskService()
    task = await service.start_task(
        db=db,
        task_id=task_id,
        operator_id=current_user.id
    )
    return task


@router.post("/{task_id}/photos")
async def upload_task_photo(
    task_id: int,
    photo_type: str = Query(..., regex="^(before|after|problem)$"),
    file: UploadFile = File(...),
    description: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    storage: StorageService = Depends()
):
    """Загрузить фото задачи"""
    # Сохранение файла
    photo_url = await storage.upload_file(
        file=file,
        folder=f"tasks/{task_id}/{photo_type}"
    )
    
    service = TaskService()
    photo = await service.add_task_photo(
        db=db,
        task_id=task_id,
        photo_data=TaskPhotoCreate(
            photo_type=photo_type,
            photo_url=photo_url,
            description=description
        ),
        uploaded_by_id=current_user.id
    )
    
    return photo


@router.post("/{task_id}/problems")
async def report_problem(
    task_id: int,
    problem_data: TaskProblemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Сообщить о проблеме"""
    service = TaskService()
    problem = await service.report_problem(
        db=db,
        task_id=task_id,
        problem_data=problem_data,
        reported_by_id=current_user.id
    )
    return problem


@router.post("/{task_id}/complete")
async def complete_task(
    task_id: int,
    notes: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Завершить задачу"""
    service = TaskService()
    task = await service.complete_task(
        db=db,
        task_id=task_id,
        operator_id=current_user.id,
        notes=notes
    )
    return task


@router.get("/statistics/summary")
@require_permissions(["tasks.view_statistics"])
async def get_task_statistics(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить статистику задач"""
    service = TaskService()
    stats = await service.get_task_statistics(
        db=db,
        date_from=date_from,
        date_to=date_to
    )
    return stats


# Routes endpoints

@router.post("/routes", response_model=RouteResponse)
@require_permissions(["routes.create"])
async def create_route(
    route_data: RouteCreate,
    task_ids: List[int],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Создать маршрут"""
    service = RouteService()
    route = await service.create_route(
        db=db,
        route_data=route_data,
        task_ids=task_ids,
        current_user=current_user
    )
    return route


@router.get("/routes", response_model=List[RouteResponse])
async def get_routes(
    status: Optional[str] = Query(None),
    date: Optional[datetime] = Query(None),
    assigned_to: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить список маршрутов"""
    service = RouteService()
    
    # Фильтрация по правам
    if 'operator' in [r.name for r in current_user.roles]:
        assigned_to = current_user.id
    
    routes = await service.get_list(
        db=db,
        filters={
            'status': status,
            'date': date,
            'assigned_to_id': assigned_to
        }
    )
    return routes


@router.get("/routes/{route_id}")
async def get_route(
    route_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить детали маршрута"""
    service = RouteService()
    route = await service.get(db, route_id)
    
    if not route:
        raise HTTPException(status_code=404, detail="Маршрут не найден")
    
    # Проверка прав доступа
    if 'admin' not in [r.name for r in current_user.roles] and \
       'manager' not in [r.name for r in current_user.roles] and \
       route.assigned_to_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа к этому маршруту")
    
    return route


@router.post("/routes/{route_id}/assign")
@require_permissions(["routes.assign"])
async def assign_route(
    route_id: int,
    operator_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Назначить маршрут оператору"""
    service = RouteService()
    route = await service.assign_route(
        db=db,
        route_id=route_id,
        operator_id=operator_id,
        current_user=current_user
    )
    return route


@router.post("/routes/{route_id}/start")
async def start_route(
    route_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Начать выполнение маршрута"""
    service = RouteService()
    route = await service.start_route(
        db=db,
        route_id=route_id,
        operator_id=current_user.id
    )
    return route


@router.get("/routes/{route_id}/progress")
async def get_route_progress(
    route_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить прогресс маршрута"""
    service = RouteService()
    progress = await service.get_route_progress(db, route_id)
    return progress


@router.post("/routes/{route_id}/complete")
async def complete_route(
    route_id: int,
    notes: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Завершить маршрут"""
    service = RouteService()
    route = await service.complete_route(
        db=db,
        route_id=route_id,
        operator_id=current_user.id,
        notes=notes
    )
    return route