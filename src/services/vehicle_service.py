# src/services/vehicle_service.py

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..db.models import VehicleLog, User, Vehicle
from ..db.schemas import VehicleLogCreate, VehicleLogUpdate
from ..core.exceptions import NotFoundError, ValidationError
from ..utils.cache import cache_result, invalidate_cache
from .base import BaseService


class VehicleService(BaseService[VehicleLog, VehicleLogCreate, VehicleLogUpdate]):
    """Сервис для управления транспортом"""
    
    model = VehicleLog
    
    async def add_mileage_log(
        self,
        db: AsyncSession,
        vehicle_id: int,
        log_data: VehicleLogCreate,
        driver_id: int,
        odometer_photo: Optional[str] = None
    ) -> VehicleLog:
        """Добавление записи о пробеге"""
        # Проверка транспорта
        vehicle = await db.get(Vehicle, vehicle_id)
        if not vehicle:
            raise NotFoundError(f"Транспорт {vehicle_id} не найден")
        
        # Проверка последнего показания одометра
        last_log = await db.execute(
            select(VehicleLog)
            .where(
                and_(
                    VehicleLog.vehicle_id == vehicle_id,
                    VehicleLog.log_type == 'mileage'
                )
            ).order_by(VehicleLog.log_date.desc())
            .limit(1)
        )
        last = last_log.scalar_one_or_none()
        
        if last and log_data.odometer_reading <= last.odometer_reading:
            raise ValidationError(
                f"Показание одометра должно быть больше предыдущего ({last.odometer_reading} км)"
            )
        
        # Расчет пробега
        mileage = 0
        if last:
            mileage = log_data.odometer_reading - last.odometer_reading
        
        # Создание записи
        log = VehicleLog(
            vehicle_id=vehicle_id,
            driver_id=driver_id,
            log_type='mileage',
            log_date=log_data.log_date or datetime.now(timezone.utc),
            odometer_reading=log_data.odometer_reading,
            mileage=mileage,
            odometer_photo_url=odometer_photo,
            notes=log_data.notes,
            action_timestamp=log_data.action_timestamp or datetime.now(timezone.utc)
        )
        
        # Обновление общего пробега автомобиля
        vehicle.current_mileage = log_data.odometer_reading
        
        db.add(log)
        await db.commit()
        await db.refresh(log)
        
        await invalidate_cache(f"vehicle:{vehicle_id}:logs")
        return log
    
    async def add_fuel_log(
        self,
        db: AsyncSession,
        vehicle_id: int,
        log_data: VehicleLogCreate,
        driver_id: int,
        receipt_photo: Optional[str] = None
    ) -> VehicleLog:
        """Добавление записи о заправке"""
        # Проверка транспорта
        vehicle = await db.get(Vehicle, vehicle_id)
        if not vehicle:
            raise NotFoundError(f"Транспорт {vehicle_id} не найден")
        
        if not log_data.fuel_amount or not log_data.fuel_cost:
            raise ValidationError("Необходимо указать количество топлива и стоимость")
        
        # Расчет цены за литр
        fuel_price = log_data.fuel_cost / log_data.fuel_amount
        
        # Создание записи
        log = VehicleLog(
            vehicle_id=vehicle_id,
            driver_id=driver_id,
            log_type='fuel',
            log_date=log_data.log_date or datetime.now(timezone.utc),
            fuel_amount=log_data.fuel_amount,
            fuel_cost=log_data.fuel_cost,
            fuel_price_per_liter=fuel_price,
            fuel_station=log_data.fuel_station,
            receipt_photo_url=receipt_photo,
            notes=log_data.notes,
            action_timestamp=log_data.action_timestamp or datetime.now(timezone.utc)
        )
        
        db.add(log)
        await db.commit()
        await db.refresh(log)
        
        await invalidate_cache(f"vehicle:{vehicle_id}:logs")
        return log
    
    async def get_vehicle_logs(
        self,
        db: AsyncSession,
        vehicle_id: int,
        log_type: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> List[VehicleLog]:
        """Получить журнал транспорта"""
        query = select(VehicleLog).where(
            VehicleLog.vehicle_id == vehicle_id
        )
        
        if log_type:
            query = query.where(VehicleLog.log_type == log_type)
        
        if date_from:
            query = query.where(VehicleLog.log_date >= date_from)
        
        if date_to:
            query = query.where(VehicleLog.log_date <= date_to)
        
        query = query.options(
            selectinload(VehicleLog.driver)
        ).order_by(VehicleLog.log_date.desc())
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def get_driver_logs(
        self,
        db: AsyncSession,
        driver_id: int,
        date_from: Optional[datetime] = None
    ) -> List[VehicleLog]:
        """Получить записи водителя"""
        query = select(VehicleLog).where(
            VehicleLog.driver_id == driver_id
        )
        
        if date_from:
            query = query.where(VehicleLog.log_date >= date_from)
        
        query = query.options(
            selectinload(VehicleLog.vehicle)
        ).order_by(VehicleLog.log_date.desc())
        
        result = await db.execute(query)
        return result.scalars().all()
    
    @cache_result(expire=300)
    async def calculate_fuel_consumption(
        self,
        db: AsyncSession,
        vehicle_id: int,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """Расчет расхода топлива"""
        date_from = datetime.now(timezone.utc) - timedelta(days=period_days)
        
        # Общий пробег за период
        mileage_logs = await db.execute(
            select(
                func.sum(VehicleLog.mileage).label('total_mileage')
            ).where(
                and_(
                    VehicleLog.vehicle_id == vehicle_id,
                    VehicleLog.log_type == 'mileage',
                    VehicleLog.log_date >= date_from
                )
            )
        )
        total_mileage = mileage_logs.scalar() or 0
        
        # Общее топливо за период
        fuel_logs = await db.execute(
            select(
                func.sum(VehicleLog.fuel_amount).label('total_fuel'),
                func.sum(VehicleLog.fuel_cost).label('total_cost'),
                func.avg(VehicleLog.fuel_price_per_liter).label('avg_price')
            ).where(
                and_(
                    VehicleLog.vehicle_id == vehicle_id,
                    VehicleLog.log_type == 'fuel',
                    VehicleLog.log_date >= date_from
                )
            )
        )
        fuel_stats = fuel_logs.one()
        
        # Расчет расхода
        consumption = 0
        if total_mileage > 0 and fuel_stats.total_fuel:
            consumption = float(fuel_stats.total_fuel) / float(total_mileage) * 100
        
        return {
            'period_days': period_days,
            'total_mileage': float(total_mileage),
            'total_fuel': float(fuel_stats.total_fuel or 0),
            'total_fuel_cost': float(fuel_stats.total_cost or 0),
            'average_fuel_price': float(fuel_stats.avg_price or 0),
            'fuel_consumption_per_100km': round(consumption, 2)
        }
    
    @cache_result(expire=300)
    async def get_vehicle_statistics(
        self,
        db: AsyncSession,
        vehicle_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Статистика по транспорту"""
        base_query = select(VehicleLog)
        if vehicle_id:
            base_query = base_query.where(VehicleLog.vehicle_id == vehicle_id)
        
        # Статистика за последний месяц
        month_ago = datetime.now(timezone.utc) - timedelta(days=30)
        
        # Пробег
        mileage_stats = await db.execute(
            base_query.with_only_columns(
                func.count(VehicleLog.id).label('count'),
                func.sum(VehicleLog.mileage).label('total')
            ).where(
                and_(
                    VehicleLog.log_type == 'mileage',
                    VehicleLog.log_date >= month_ago
                )
            )
        )
        mileage = mileage_stats.one()
        
        # Заправки
        fuel_stats = await db.execute(
            base_query.with_only_columns(
                func.count(VehicleLog.id).label('count'),
                func.sum(VehicleLog.fuel_amount).label('total_fuel'),
                func.sum(VehicleLog.fuel_cost).label('total_cost')
            ).where(
                and_(
                    VehicleLog.log_type == 'fuel',
                    VehicleLog.log_date >= month_ago
                )
            )
        )
        fuel = fuel_stats.one()
        
        # По водителям
        by_driver = await db.execute(
            select(
                User.id,
                User.full_name,
                func.sum(VehicleLog.mileage).label('total_mileage'),
                func.count(VehicleLog.id).label('trips')
            ).join(User, VehicleLog.driver_id == User.id)
            .where(
                and_(
                    VehicleLog.log_type == 'mileage',
                    VehicleLog.log_date >= month_ago
                )
            ).group_by(User.id, User.full_name)
            .order_by(func.sum(VehicleLog.mileage).desc())
            .limit(10)
        )
        
        return {
            'last_month': {
                'mileage': {
                    'trips': mileage.count or 0,
                    'total_km': float(mileage.total or 0)
                },
                'fuel': {
                    'refills': fuel.count or 0,
                    'total_liters': float(fuel.total_fuel or 0),
                    'total_cost': float(fuel.total_cost or 0)
                }
            },
            'by_driver': [
                {
                    'driver_id': row.id,
                    'driver_name': row.full_name,
                    'total_mileage': float(row.total_mileage or 0),
                    'trips': row.trips
                }
                for row in by_driver
            ]
        }
    
    async def check_maintenance_needed(
        self,
        db: AsyncSession,
        vehicle_id: int
    ) -> Dict[str, Any]:
        """Проверка необходимости ТО транспорта"""
        vehicle = await db.get(Vehicle, vehicle_id)
        if not vehicle:
            raise NotFoundError(f"Транспорт {vehicle_id} не найден")
        
        # Пробег с последнего ТО
        mileage_since_maintenance = vehicle.current_mileage - vehicle.last_maintenance_mileage
        
        # Дней с последнего ТО
        days_since_maintenance = 0
        if vehicle.last_maintenance_date:
            days_since_maintenance = (
                datetime.now(timezone.utc).date() - vehicle.last_maintenance_date
            ).days
        
        # Проверка критериев
        maintenance_needed = False
        reasons = []
        
        if vehicle.maintenance_interval_km and mileage_since_maintenance >= vehicle.maintenance_interval_km:
            maintenance_needed = True
            reasons.append(f"Превышен интервал пробега: {mileage_since_maintenance} км")
        
        if vehicle.maintenance_interval_days and days_since_maintenance >= vehicle.maintenance_interval_days:
            maintenance_needed = True
            reasons.append(f"Превышен временной интервал: {days_since_maintenance} дней")
        
        return {
            'vehicle_id': vehicle_id,
            'maintenance_needed': maintenance_needed,
            'mileage_since_maintenance': mileage_since_maintenance,
            'days_since_maintenance': days_since_maintenance,
            'reasons': reasons
        }