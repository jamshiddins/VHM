# src/services/maintenance_service.py

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..db.models import (
    MaintenanceSchedule, MaintenanceHistory, Machine,
    User, MachineTask
)
from ..db.schemas import (
    MaintenanceScheduleCreate, MaintenanceScheduleUpdate,
    MaintenanceHistoryCreate
)
from ..core.exceptions import NotFoundError, ValidationError
from ..utils.cache import cache_result, invalidate_cache
from .base import BaseService


class MaintenanceService(BaseService[MaintenanceSchedule, MaintenanceScheduleCreate, MaintenanceScheduleUpdate]):
    """Сервис для управления техническим обслуживанием"""
    
    model = MaintenanceSchedule
    
    async def create_maintenance_schedule(
        self,
        db: AsyncSession,
        schedule_data: MaintenanceScheduleCreate,
        current_user: User
    ) -> MaintenanceSchedule:
        """Создание графика ТО"""
        # Проверка автомата
        machine = await db.get(Machine, schedule_data.machine_id)
        if not machine:
            raise NotFoundError(f"Автомат {schedule_data.machine_id} не найден")
        
        # Проверка существующего активного графика
        existing = await db.execute(
            select(MaintenanceSchedule).where(
                and_(
                    MaintenanceSchedule.machine_id == schedule_data.machine_id,
                    MaintenanceSchedule.is_active == True
                )
            )
        )
        if existing.scalar_one_or_none():
            raise ValidationError("У автомата уже есть активный график ТО")
        
        # Расчет следующей даты
        next_date = self._calculate_next_date(
            datetime.now(timezone.utc).date(),
            schedule_data.frequency_type,
            schedule_data.frequency_value
        )
        
        schedule = MaintenanceSchedule(
            **schedule_data.model_dump(),
            next_maintenance_date=next_date,
            created_by_id=current_user.id
        )
        
        db.add(schedule)
        await db.commit()
        await db.refresh(schedule)
        
        await invalidate_cache(f"machine:{schedule_data.machine_id}:maintenance")
        return schedule
    
    async def perform_maintenance(
        self,
        db: AsyncSession,
        schedule_id: int,
        history_data: MaintenanceHistoryCreate,
        performed_by_id: int,
        photos: Optional[List[str]] = None
    ) -> MaintenanceHistory:
        """Выполнение ТО"""
        schedule = await self.get(db, schedule_id)
        if not schedule:
            raise NotFoundError(f"График ТО {schedule_id} не найден")
        
        if not schedule.is_active:
            raise ValidationError("График ТО неактивен")
        
        # Создание записи истории
        history = MaintenanceHistory(
            schedule_id=schedule_id,
            machine_id=schedule.machine_id,
            performed_date=history_data.performed_date or datetime.now(timezone.utc),
            performed_by_id=performed_by_id,
            checklist_completed=history_data.checklist_completed or {},
            notes=history_data.notes,
            photos=photos or []
        )
        
        # Подсчет выполненных пунктов
        total_items = len(schedule.checklist_items)
        completed_items = sum(
            1 for item in history_data.checklist_completed.values() 
            if item is True
        )
        
        history.completion_rate = (completed_items / total_items * 100) if total_items > 0 else 100
        
        # Обновление даты следующего ТО
        schedule.last_maintenance_date = history.performed_date.date()
        schedule.next_maintenance_date = self._calculate_next_date(
            schedule.last_maintenance_date,
            schedule.frequency_type,
            schedule.frequency_value
        )
        
        db.add(history)
        await db.commit()
        await db.refresh(history)
        
        await invalidate_cache(f"machine:{schedule.machine_id}:maintenance")
        return history
    
    async def get_overdue_maintenance(
        self,
        db: AsyncSession,
        days_overdue: int = 0
    ) -> List[MaintenanceSchedule]:
        """Получить просроченные ТО"""
        cutoff_date = datetime.now(timezone.utc).date() - timedelta(days=days_overdue)
        
        result = await db.execute(
            select(MaintenanceSchedule)
            .where(
                and_(
                    MaintenanceSchedule.is_active == True,
                    MaintenanceSchedule.next_maintenance_date <= cutoff_date
                )
            ).options(
                selectinload(MaintenanceSchedule.machine)
            ).order_by(MaintenanceSchedule.next_maintenance_date)
        )
        return result.scalars().all()
    
    async def get_upcoming_maintenance(
        self,
        db: AsyncSession,
        days_ahead: int = 7
    ) -> List[MaintenanceSchedule]:
        """Получить предстоящие ТО"""
        start_date = datetime.now(timezone.utc).date()
        end_date = start_date + timedelta(days=days_ahead)
        
        result = await db.execute(
            select(MaintenanceSchedule)
            .where(
                and_(
                    MaintenanceSchedule.is_active == True,
                    MaintenanceSchedule.next_maintenance_date >= start_date,
                    MaintenanceSchedule.next_maintenance_date <= end_date
                )
            ).options(
                selectinload(MaintenanceSchedule.machine)
            ).order_by(MaintenanceSchedule.next_maintenance_date)
        )
        return result.scalars().all()
    
    async def create_maintenance_tasks(
        self,
        db: AsyncSession,
        current_user: User
    ) -> List[MachineTask]:
        """Создание задач ТО для просроченных графиков"""
        overdue = await self.get_overdue_maintenance(db)
        created_tasks = []
        
        for schedule in overdue:
            # Проверка существующей задачи
            existing_task = await db.execute(
                select(MachineTask).where(
                    and_(
                        MachineTask.machine_id == schedule.machine_id,
                        MachineTask.task_type == 'maintenance',
                        MachineTask.status.in_(['pending', 'assigned', 'in_progress'])
                    )
                )
            )
            
            if not existing_task.scalar_one_or_none():
                # Создание задачи ТО
                task = MachineTask(
                    machine_id=schedule.machine_id,
                    task_type='maintenance',
                    status='pending',
                    priority='high' if schedule.next_maintenance_date < datetime.now(timezone.utc).date() - timedelta(days=7) else 'medium',
                    scheduled_date=datetime.now(timezone.utc),
                    description=f"Плановое ТО: {schedule.maintenance_type}",
                    metadata={
                        'schedule_id': schedule.id,
                        'checklist_items': schedule.checklist_items
                    },
                    created_by_id=current_user.id
                )
                db.add(task)
                created_tasks.append(task)
        
        if created_tasks:
            await db.commit()
            await invalidate_cache("tasks:*")
        
        return created_tasks
    
    async def get_maintenance_history(
        self,
        db: AsyncSession,
        machine_id: int,
        limit: int = 50
    ) -> List[MaintenanceHistory]:
        """История ТО автомата"""
        result = await db.execute(
            select(MaintenanceHistory)
            .where(MaintenanceHistory.machine_id == machine_id)
            .options(
                selectinload(MaintenanceHistory.performed_by),
                selectinload(MaintenanceHistory.schedule)
            )
            .order_by(MaintenanceHistory.performed_date.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    @cache_result(expire=300)
    async def get_maintenance_statistics(
        self,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Статистика техобслуживания"""
        # Активные графики
        active_schedules = await db.scalar(
            select(func.count(MaintenanceSchedule.id))
            .where(MaintenanceSchedule.is_active == True)
        )
        
        # Просроченные ТО
        overdue_count = await db.scalar(
            select(func.count(MaintenanceSchedule.id))
            .where(
                and_(
                    MaintenanceSchedule.is_active == True,
                    MaintenanceSchedule.next_maintenance_date < datetime.now(timezone.utc).date()
                )
            )
        )
        
        # Статистика выполнения за последний месяц
        month_ago = datetime.now(timezone.utc) - timedelta(days=30)
        
        completion_stats = await db.execute(
            select(
                func.count(MaintenanceHistory.id).label('total'),
                func.avg(MaintenanceHistory.completion_rate).label('avg_completion')
            ).where(
                MaintenanceHistory.performed_date >= month_ago
            )
        )
        stats = completion_stats.one()
        
        # По типам ТО
        by_type = await db.execute(
            select(
                MaintenanceSchedule.maintenance_type,
                func.count(MaintenanceSchedule.id).label('count')
            ).where(MaintenanceSchedule.is_active == True)
            .group_by(MaintenanceSchedule.maintenance_type)
        )
        
        # Топ исполнителей
        top_performers = await db.execute(
            select(
                User.id,
                User.full_name,
                func.count(MaintenanceHistory.id).label('count'),
                func.avg(MaintenanceHistory.completion_rate).label('avg_rate')
            ).join(User, MaintenanceHistory.performed_by_id == User.id)
            .where(MaintenanceHistory.performed_date >= month_ago)
            .group_by(User.id, User.full_name)
            .order_by(func.count(MaintenanceHistory.id).desc())
            .limit(5)
        )
        
        return {
            'active_schedules': active_schedules,
            'overdue_count': overdue_count,
            'overdue_percentage': (overdue_count / active_schedules * 100) if active_schedules > 0 else 0,
            'last_month': {
                'total_performed': stats.total or 0,
                'average_completion_rate': float(stats.avg_completion or 0)
            },
            'by_type': {
                row.maintenance_type: row.count 
                for row in by_type
            },
            'top_performers': [
                {
                    'user_id': row.id,
                    'name': row.full_name,
                    'count': row.count,
                    'average_rate': float(row.avg_rate)
                }
                for row in top_performers
            ]
        }
    
    def _calculate_next_date(
        self,
        from_date: datetime.date,
        frequency_type: str,
        frequency_value: int
    ) -> datetime.date:
        """Расчет следующей даты ТО"""
        if frequency_type == 'days':
            return from_date + timedelta(days=frequency_value)
        elif frequency_type == 'weeks':
            return from_date + timedelta(weeks=frequency_value)
        elif frequency_type == 'months':
            # Примерный расчет месяцев
            return from_date + timedelta(days=frequency_value * 30)
        else:
            raise ValueError(f"Неизвестный тип частоты: {frequency_type}")