# src/services/bunker_service.py

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..db.models import Bunker, BunkerWeighing, User, Machine, Bag, BagItem
from ..db.schemas import BunkerCreate, BunkerUpdate, BunkerWeighingCreate
from ..core.exceptions import NotFoundError, ValidationError, PermissionError
from ..utils.cache import cache_result, invalidate_cache
from .base import BaseService


class BunkerService(BaseService[Bunker, BunkerCreate, BunkerUpdate]):
    """Сервис для управления бункерами"""
    
    model = Bunker
    
    async def create_bunker(
        self,
        db: AsyncSession,
        bunker_data: BunkerCreate,
        current_user: User
    ) -> Bunker:
        """Создание нового бункера"""
        # Проверка уникальности кода
        existing = await db.execute(
            select(Bunker).where(Bunker.code == bunker_data.code)
        )
        if existing.scalar_one_or_none():
            raise ValidationError(f"Бункер с кодом {bunker_data.code} уже существует")
        
        bunker = Bunker(
            **bunker_data.model_dump(),
            created_by_id=current_user.id
        )
        db.add(bunker)
        await db.commit()
        await db.refresh(bunker)
        
        await invalidate_cache("bunkers:*")
        return bunker
    
    async def get_bunkers_by_status(
        self,
        db: AsyncSession,
        status: str,
        include_weighings: bool = False
    ) -> List[Bunker]:
        """Получить бункеры по статусу"""
        query = select(Bunker).where(Bunker.status == status)
        
        if include_weighings:
            query = query.options(selectinload(Bunker.weighings))
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def get_bunkers_for_cleaning(
        self,
        db: AsyncSession,
        max_cycles: int = 10
    ) -> List[Bunker]:
        """Получить бункеры, требующие мойки"""
        result = await db.execute(
            select(Bunker).where(
                and_(
                    Bunker.use_cycles >= max_cycles,
                    Bunker.status != 'maintenance'
                )
            )
        )
        return result.scalars().all()
    
    async def weigh_bunker(
        self,
        db: AsyncSession,
        bunker_id: int,
        weighing_data: BunkerWeighingCreate,
        current_user: User,
        photo_url: Optional[str] = None
    ) -> BunkerWeighing:
        """Взвешивание бункера с расчетом чистого веса"""
        bunker = await self.get(db, bunker_id)
        if not bunker:
            raise NotFoundError(f"Бункер {bunker_id} не найден")
        
        # Расчет чистого веса
        net_weight = weighing_data.gross_weight - bunker.empty_weight
        
        if net_weight < 0:
            raise ValidationError("Вес брутто меньше веса тары!")
        
        # Создание записи взвешивания
        weighing = BunkerWeighing(
            bunker_id=bunker_id,
            ingredient_id=weighing_data.ingredient_id,
            gross_weight=weighing_data.gross_weight,
            net_weight=net_weight,
            photo_url=photo_url,
            performed_by_id=current_user.id,
            action_timestamp=weighing_data.action_timestamp or datetime.now(timezone.utc)
        )
        
        # Обновление статуса бункера
        bunker.status = 'filled'
        bunker.current_ingredient_id = weighing_data.ingredient_id
        bunker.last_filled_at = weighing.action_timestamp
        
        db.add(weighing)
        await db.commit()
        await db.refresh(weighing)
        
        await invalidate_cache(f"bunker:{bunker_id}")
        return weighing
    
    async def assign_to_bag(
        self,
        db: AsyncSession,
        bunker_id: int,
        bag_id: int,
        current_user: User
    ) -> BagItem:
        """Привязка бункера к сумке"""
        bunker = await self.get(db, bunker_id)
        if not bunker:
            raise NotFoundError(f"Бункер {bunker_id} не найден")
        
        if bunker.status != 'filled':
            raise ValidationError("Можно привязать только заполненный бункер")
        
        # Проверка существования сумки
        bag_result = await db.execute(
            select(Bag).where(Bag.id == bag_id)
        )
        bag = bag_result.scalar_one_or_none()
        if not bag:
            raise NotFoundError(f"Сумка {bag_id} не найдена")
        
        if bag.status != 'preparing':
            raise ValidationError("Сумка должна быть в статусе подготовки")
        
        # Создание элемента сумки
        bag_item = BagItem(
            bag_id=bag_id,
            bunker_id=bunker_id,
            item_type='bunker',
            quantity=1
        )
        
        # Обновление статуса бункера
        bunker.status = 'in_bag'
        bunker.current_bag_id = bag_id
        
        db.add(bag_item)
        await db.commit()
        
        await invalidate_cache(f"bunker:{bunker_id}")
        await invalidate_cache(f"bag:{bag_id}")
        
        return bag_item
    
    async def return_from_operator(
        self,
        db: AsyncSession,
        bunker_id: int,
        operator_id: int,
        is_empty: bool,
        current_user: User
    ) -> Bunker:
        """Возврат бункера от оператора"""
        bunker = await self.get(db, bunker_id)
        if not bunker:
            raise NotFoundError(f"Бункер {bunker_id} не найден")
        
        if bunker.status != 'in_use':
            raise ValidationError("Бункер не находится в использовании")
        
        # Увеличиваем счетчик циклов
        bunker.use_cycles += 1
        
        # Обновляем статус
        if is_empty:
            bunker.status = 'empty'
            bunker.current_ingredient_id = None
        else:
            bunker.status = 'filled'
        
        bunker.current_bag_id = None
        bunker.last_returned_at = datetime.now(timezone.utc)
        
        await db.commit()
        await db.refresh(bunker)
        
        await invalidate_cache(f"bunker:{bunker_id}")
        return bunker
    
    async def mark_for_cleaning(
        self,
        db: AsyncSession,
        bunker_id: int,
        current_user: User
    ) -> Bunker:
        """Отправить бункер на мойку"""
        bunker = await self.get(db, bunker_id)
        if not bunker:
            raise NotFoundError(f"Бункер {bunker_id} не найден")
        
        if bunker.status not in ['empty', 'filled']:
            raise ValidationError("Бункер должен быть свободен для отправки на мойку")
        
        bunker.status = 'maintenance'
        bunker.use_cycles = 0  # Сброс счетчика после мойки
        bunker.last_cleaned_at = datetime.now(timezone.utc)
        
        await db.commit()
        await db.refresh(bunker)
        
        await invalidate_cache(f"bunker:{bunker_id}")
        return bunker
    
    @cache_result(expire=300)
    async def get_bunker_statistics(
        self,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Статистика по бункерам"""
        # Общее количество по статусам
        status_counts = await db.execute(
            select(
                Bunker.status,
                func.count(Bunker.id).label('count')
            ).group_by(Bunker.status)
        )
        
        # Бункеры требующие мойки
        need_cleaning = await db.execute(
            select(func.count(Bunker.id)).where(
                Bunker.use_cycles >= 10
            )
        )
        
        # Средний вес по ингредиентам
        avg_weights = await db.execute(
            select(
                BunkerWeighing.ingredient_id,
                func.avg(BunkerWeighing.net_weight).label('avg_weight'),
                func.count(BunkerWeighing.id).label('count')
            ).group_by(BunkerWeighing.ingredient_id)
            .order_by(func.count(BunkerWeighing.id).desc())
            .limit(10)
        )
        
        return {
            'status_distribution': {
                row.status: row.count 
                for row in status_counts
            },
            'need_cleaning': need_cleaning.scalar(),
            'average_weights': [
                {
                    'ingredient_id': row.ingredient_id,
                    'avg_weight': float(row.avg_weight) if row.avg_weight else 0,
                    'count': row.count
                }
                for row in avg_weights
            ],
            'total_bunkers': await db.scalar(
                select(func.count(Bunker.id))
            )
        }
    
    async def get_bunker_history(
        self,
        db: AsyncSession,
        bunker_id: int,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """История операций с бункером"""
        # Взвешивания
        weighings = await db.execute(
            select(BunkerWeighing)
            .where(BunkerWeighing.bunker_id == bunker_id)
            .order_by(BunkerWeighing.action_timestamp.desc())
            .limit(limit)
            .options(
                selectinload(BunkerWeighing.ingredient),
                selectinload(BunkerWeighing.performed_by)
            )
        )
        
        history = []
        for w in weighings.scalars():
            history.append({
                'type': 'weighing',
                'timestamp': w.action_timestamp,
                'data': {
                    'ingredient': w.ingredient.name,
                    'gross_weight': w.gross_weight,
                    'net_weight': w.net_weight,
                    'performed_by': w.performed_by.full_name
                }
            })
        
        return sorted(history, key=lambda x: x['timestamp'], reverse=True)