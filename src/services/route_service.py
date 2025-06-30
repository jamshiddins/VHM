# src/services/route_service.py

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import math

from ..db.models import Route, MachineTask, Machine, User
from ..db.schemas import RouteCreate, RouteUpdate
from ..core.exceptions import NotFoundError, ValidationError
from ..utils.cache import cache_result, invalidate_cache
from .base import BaseService


class RouteService(BaseService[Route, RouteCreate, RouteUpdate]):
    """Сервис для управления маршрутами"""
    
    model = Route
    
    async def create_route(
        self,
        db: AsyncSession,
        route_data: RouteCreate,
        task_ids: List[int],
        current_user: User
    ) -> Route:
        """Создание маршрута с задачами"""
        # Проверка задач
        tasks = await db.execute(
            select(MachineTask)
            .where(MachineTask.id.in_(task_ids))
            .options(selectinload(MachineTask.machine))
        )
        tasks = tasks.scalars().all()
        
        if len(tasks) != len(task_ids):
            raise ValidationError("Некоторые задачи не найдены")
        
        # Проверка статусов задач
        for task in tasks:
            if task.status not in ['pending', 'assigned']:
                raise ValidationError(f"Задача {task.id} уже выполняется или завершена")
        
        # Оптимизация порядка задач
        optimized_tasks = await self._optimize_route(tasks)
        
        # Расчет расстояния и времени
        total_distance, estimated_duration = await self._calculate_route_metrics(
            optimized_tasks
        )
        
        # Создание маршрута
        route = Route(
            **route_data.model_dump(),
            total_distance=total_distance,
            estimated_duration=estimated_duration,
            created_by_id=current_user.id
        )
        
        db.add(route)
        await db.flush()
        
        # Привязка задач к маршруту
        for idx, task in enumerate(optimized_tasks):
            task.route_id = route.id
            task.order_in_route = idx + 1
            task.status = 'assigned' if route.assigned_to_id else 'pending'
        
        await db.commit()
        await db.refresh(route)
        
        await invalidate_cache("routes:*")
        await invalidate_cache("tasks:*")
        
        return route
    
    async def assign_route(
        self,
        db: AsyncSession,
        route_id: int,
        operator_id: int,
        current_user: User
    ) -> Route:
        """Назначение маршрута оператору"""
        route = await db.execute(
            select(Route)
            .where(Route.id == route_id)
            .options(selectinload(Route.tasks))
        )
        route = route.scalar_one_or_none()
        
        if not route:
            raise NotFoundError(f"Маршрут {route_id} не найден")
        
        if route.status != 'pending':
            raise ValidationError("Маршрут уже назначен или выполняется")
        
        # Проверка оператора
        operator = await db.get(User, operator_id)
        if not operator or 'operator' not in [r.name for r in operator.roles]:
            raise ValidationError("Пользователь не является оператором")
        
        # Обновление маршрута
        route.assigned_to_id = operator_id
        route.status = 'assigned'
        route.assigned_at = datetime.now(timezone.utc)
        
        # Обновление задач
        for task in route.tasks:
            task.assigned_to_id = operator_id
            task.status = 'assigned'
        
        await db.commit()
        await db.refresh(route)
        
        await invalidate_cache(f"route:{route_id}")
        await invalidate_cache(f"operator:{operator_id}:routes")
        
        return route
    
    async def start_route(
        self,
        db: AsyncSession,
        route_id: int,
        operator_id: int
    ) -> Route:
        """Начало выполнения маршрута"""
        route = await self.get(db, route_id)
        if not route:
            raise NotFoundError(f"Маршрут {route_id} не найден")
        
        if route.assigned_to_id != operator_id:
            raise PermissionError("Маршрут назначен другому оператору")
        
        if route.status != 'assigned':
            raise ValidationError("Маршрут уже выполняется или завершен")
        
        route.status = 'in_progress'
        route.started_at = datetime.now(timezone.utc)
        
        await db.commit()
        await db.refresh(route)
        
        await invalidate_cache(f"route:{route_id}")
        return route
    
    async def complete_route(
        self,
        db: AsyncSession,
        route_id: int,
        operator_id: int,
        notes: Optional[str] = None
    ) -> Route:
        """Завершение маршрута"""
        route = await db.execute(
            select(Route)
            .where(Route.id == route_id)
            .options(selectinload(Route.tasks))
        )
        route = route.scalar_one_or_none()
        
        if not route:
            raise NotFoundError(f"Маршрут {route_id} не найден")
        
        if route.assigned_to_id != operator_id:
            raise PermissionError("Маршрут назначен другому оператору")
        
        if route.status != 'in_progress':
            raise ValidationError("Маршрут не выполняется")
        
        # Проверка завершенности всех задач
        incomplete_tasks = [
            task for task in route.tasks 
            if task.status not in ['completed', 'cancelled']
        ]
        
        if incomplete_tasks:
            raise ValidationError(
                f"Есть незавершенные задачи: {len(incomplete_tasks)}"
            )
        
        route.status = 'completed'
        route.completed_at = datetime.now(timezone.utc)
        route.notes = notes
        
        # Расчет фактического времени
        if route.started_at:
            route.actual_duration = int(
                (route.completed_at - route.started_at).total_seconds() / 60
            )
        
        await db.commit()
        await db.refresh(route)
        
        await invalidate_cache(f"route:{route_id}")
        await invalidate_cache(f"operator:{operator_id}:routes")
        
        return route
    
    async def get_operator_routes(
        self,
        db: AsyncSession,
        operator_id: int,
        status: Optional[str] = None,
        date: Optional[datetime] = None
    ) -> List[Route]:
        """Получить маршруты оператора"""
        query = select(Route).where(
            Route.assigned_to_id == operator_id
        )
        
        if status:
            query = query.where(Route.status == status)
        
        if date:
            query = query.where(
                func.date(Route.date) == date.date()
            )
        
        query = query.options(
            selectinload(Route.tasks).selectinload(MachineTask.machine)
        ).order_by(Route.date.desc())
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def get_route_progress(
        self,
        db: AsyncSession,
        route_id: int
    ) -> Dict[str, Any]:
        """Прогресс выполнения маршрута"""
        route = await db.execute(
            select(Route)
            .where(Route.id == route_id)
            .options(selectinload(Route.tasks))
        )
        route = route.scalar_one_or_none()
        
        if not route:
            raise NotFoundError(f"Маршрут {route_id} не найден")
        
        total_tasks = len(route.tasks)
        completed_tasks = sum(
            1 for task in route.tasks 
            if task.status == 'completed'
        )
        in_progress_tasks = sum(
            1 for task in route.tasks 
            if task.status == 'in_progress'
        )
        
        progress = {
            'route_id': route_id,
            'status': route.status,
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'in_progress_tasks': in_progress_tasks,
            'pending_tasks': total_tasks - completed_tasks - in_progress_tasks,
            'completion_percentage': (
                completed_tasks / total_tasks * 100
            ) if total_tasks > 0 else 0,
            'tasks': []
        }
        
        for task in sorted(route.tasks, key=lambda t: t.order_in_route):
            progress['tasks'].append({
                'id': task.id,
                'order': task.order_in_route,
                'type': task.task_type,
                'status': task.status,
                'machine': {
                    'id': task.machine.id,
                    'name': task.machine.name,
                    'location': task.machine.location
                }
            })
        
        return progress
    
    @cache_result(expire=300)
    async def get_route_statistics(
        self,
        db: AsyncSession,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Статистика маршрутов"""
        query = select(Route)
        
        if date_from:
            query = query.where(Route.date >= date_from)
        if date_to:
            query = query.where(Route.date <= date_to)
        
        # Общая статистика
        total_stats = await db.execute(
            query.with_only_columns(
                func.count(Route.id).label('total'),
                func.count(Route.id).filter(
                    Route.status == 'completed'
                ).label('completed'),
                func.avg(Route.actual_duration).label('avg_duration'),
                func.sum(Route.total_distance).label('total_distance')
            )
        )
        stats = total_stats.one()
        
        # По операторам
        by_operator = await db.execute(
            query.join(User, Route.assigned_to_id == User.id)
            .with_only_columns(
                User.id,
                User.full_name,
                func.count(Route.id).label('total'),
                func.count(Route.id).filter(
                    Route.status == 'completed'
                ).label('completed'),
                func.avg(Route.actual_duration).label('avg_duration')
            ).group_by(User.id, User.full_name)
            .order_by(func.count(Route.id).desc())
        )
        
        # Эффективность (план vs факт)
        efficiency = await db.execute(
            query.where(Route.status == 'completed')
            .with_only_columns(
                func.avg(
                    Route.actual_duration::float / Route.estimated_duration * 100
                ).label('avg_efficiency')
            )
        )
        
        return {
            'total_routes': stats.total or 0,
            'completed_routes': stats.completed or 0,
            'completion_rate': (
                stats.completed / stats.total * 100
            ) if stats.total else 0,
            'average_duration': float(stats.avg_duration or 0),
            'total_distance': float(stats.total_distance or 0),
            'average_efficiency': float(efficiency.scalar() or 100),
            'by_operator': [
                {
                    'operator_id': row.id,
                    'operator_name': row.full_name,
                    'total_routes': row.total,
                    'completed_routes': row.completed,
                    'average_duration': float(row.avg_duration or 0)
                }
                for row in by_operator
            ]
        }
    
    async def _optimize_route(
        self,
        tasks: List[MachineTask]
    ) -> List[MachineTask]:
        """Оптимизация порядка задач (простой алгоритм ближайшего соседа)"""
        if not tasks:
            return []
        
        # Начинаем с первой задачи
        optimized = [tasks[0]]
        remaining = tasks[1:]
        
        while remaining:
            current = optimized[-1]
            nearest = min(
                remaining,
                key=lambda t: self._calculate_distance(
                    current.machine.coordinates,
                    t.machine.coordinates
                )
            )
            optimized.append(nearest)
            remaining.remove(nearest)
        
        return optimized
    
    async def _calculate_route_metrics(
        self,
        tasks: List[MachineTask]
    ) -> Tuple[float, int]:
        """Расчет метрик маршрута"""
        if not tasks:
            return 0.0, 0
        
        total_distance = 0.0
        
        # Расстояние между задачами
        for i in range(len(tasks) - 1):
            distance = self._calculate_distance(
                tasks[i].machine.coordinates,
                tasks[i + 1].machine.coordinates
            )
            total_distance += distance
        
        # Время: 30 мин на задачу + время в пути (40 км/ч средняя скорость)
        task_time = len(tasks) * 30
        travel_time = int(total_distance / 40 * 60)  # в минутах
        estimated_duration = task_time + travel_time
        
        return total_distance, estimated_duration
    
    def _calculate_distance(
        self,
        coord1: Optional[Dict[str, float]],
        coord2: Optional[Dict[str, float]]
    ) -> float:
        """Расчет расстояния между координатами (формула гаверсинуса)"""
        if not coord1 or not coord2:
            return 0.0
        
        lat1, lon1 = coord1.get('lat', 0), coord1.get('lng', 0)
        lat2, lon2 = coord2.get('lat', 0), coord2.get('lng', 0)
        
        # Радиус Земли в км
        R = 6371.0
        
        # Конвертация в радианы
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        
        # Формула гаверсинуса
        a = (
            math.sin(dlat / 2) ** 2 +
            math.cos(lat1_rad) * math.cos(lat2_rad) *
            math.sin(dlon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c