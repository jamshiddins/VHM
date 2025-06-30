# src/services/bag_service.py

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..db.models import Bag, BagItem, User, MachineTask, Bunker, Ingredient
from ..db.schemas import BagCreate, BagUpdate, BagItemCreate
from ..core.exceptions import NotFoundError, ValidationError, PermissionError
from ..utils.cache import cache_result, invalidate_cache
from .base import BaseService


class BagService(BaseService[Bag, BagCreate, BagUpdate]):
    """Сервис для управления сумками-комплектами"""
    
    model = Bag
    
    async def create_bag_for_task(
        self,
        db: AsyncSession,
        task_id: int,
        current_user: User
    ) -> Bag:
        """Создание сумки для задачи"""
        # Проверка существования задачи
        task_result = await db.execute(
            select(MachineTask).where(MachineTask.id == task_id)
        )
        task = task_result.scalar_one_or_none()
        if not task:
            raise NotFoundError(f"Задача {task_id} не найдена")
        
        if task.bag_id:
            raise ValidationError("Для этой задачи уже создана сумка")
        
        # Создание сумки
        bag = Bag(
            task_id=task_id,
            status='preparing',
            prepared_by_id=current_user.id,
            prepared_at=datetime.now(timezone.utc)
        )
        
        db.add(bag)
        await db.flush()
        
        # Привязка сумки к задаче
        task.bag_id = bag.id
        
        await db.commit()
        await db.refresh(bag)
        
        await invalidate_cache(f"task:{task_id}")
        return bag
    
    async def add_items_to_bag(
        self,
        db: AsyncSession,
        bag_id: int,
        items: List[BagItemCreate],
        current_user: User
    ) -> List[BagItem]:
        """Добавление элементов в сумку"""
        bag = await self.get(db, bag_id)
        if not bag:
            raise NotFoundError(f"Сумка {bag_id} не найдена")
        
        if bag.status != 'preparing':
            raise ValidationError("Можно добавлять элементы только в подготавливаемую сумку")
        
        created_items = []
        
        for item_data in items:
            # Проверка типа элемента
            if item_data.item_type == 'bunker':
                # Проверка бункера
                bunker = await db.get(Bunker, item_data.bunker_id)
                if not bunker:
                    raise NotFoundError(f"Бункер {item_data.bunker_id} не найден")
                if bunker.status != 'filled':
                    raise ValidationError(f"Бункер {bunker.code} не заполнен")
                
                # Обновление статуса бункера
                bunker.status = 'in_bag'
                bunker.current_bag_id = bag_id
                
            elif item_data.item_type == 'ingredient':
                # Проверка ингредиента
                ingredient = await db.get(Ingredient, item_data.ingredient_id)
                if not ingredient:
                    raise NotFoundError(f"Ингредиент {item_data.ingredient_id} не найден")
            
            # Создание элемента сумки
            bag_item = BagItem(
                bag_id=bag_id,
                **item_data.model_dump()
            )
            db.add(bag_item)
            created_items.append(bag_item)
        
        await db.commit()
        
        await invalidate_cache(f"bag:{bag_id}")
        return created_items
    
    async def complete_bag_preparation(
        self,
        db: AsyncSession,
        bag_id: int,
        current_user: User
    ) -> Bag:
        """Завершение подготовки сумки"""
        bag = await db.execute(
            select(Bag)
            .where(Bag.id == bag_id)
            .options(selectinload(Bag.items))
        )
        bag = bag.scalar_one_or_none()
        
        if not bag:
            raise NotFoundError(f"Сумка {bag_id} не найдена")
        
        if bag.status != 'preparing':
            raise ValidationError("Сумка уже подготовлена")
        
        if not bag.items:
            raise ValidationError("Нельзя завершить подготовку пустой сумки")
        
        bag.status = 'ready'
        bag.prepared_at = datetime.now(timezone.utc)
        
        await db.commit()
        await db.refresh(bag)
        
        await invalidate_cache(f"bag:{bag_id}")
        return bag
    
    async def issue_bag_to_operator(
        self,
        db: AsyncSession,
        bag_id: int,
        operator_id: int,
        current_user: User
    ) -> Bag:
        """Выдача сумки оператору"""
        bag = await self.get(db, bag_id)
        if not bag:
            raise NotFoundError(f"Сумка {bag_id} не найдена")
        
        if bag.status != 'ready':
            raise ValidationError("Можно выдать только готовую сумку")
        
        # Проверка оператора
        operator = await db.get(User, operator_id)
        if not operator or 'operator' not in [r.name for r in operator.roles]:
            raise ValidationError("Пользователь не является оператором")
        
        bag.status = 'issued'
        bag.issued_to_id = operator_id
        bag.issued_by_id = current_user.id
        bag.issued_at = datetime.now(timezone.utc)
        
        await db.commit()
        await db.refresh(bag)
        
        await invalidate_cache(f"bag:{bag_id}")
        await invalidate_cache(f"operator:{operator_id}:bags")
        
        return bag
    
    async def verify_bag_by_operator(
        self,
        db: AsyncSession,
        bag_id: int,
        operator_id: int,
        photo_url: str,
        is_complete: bool,
        missing_items: Optional[List[int]] = None
    ) -> Bag:
        """Проверка сумки оператором"""
        bag = await db.execute(
            select(Bag)
            .where(Bag.id == bag_id)
            .options(selectinload(Bag.items))
        )
        bag = bag.scalar_one_or_none()
        
        if not bag:
            raise NotFoundError(f"Сумка {bag_id} не найдена")
        
        if bag.issued_to_id != operator_id:
            raise PermissionError("Сумка выдана другому оператору")
        
        if bag.status != 'issued':
            raise ValidationError("Сумка уже проверена")
        
        bag.status = 'checked'
        bag.checked_at = datetime.now(timezone.utc)
        bag.check_photo_url = photo_url
        bag.is_complete = is_complete
        
        # Отметка недостающих элементов
        if not is_complete and missing_items:
            for item in bag.items:
                if item.id in missing_items:
                    item.is_missing = True
        
        await db.commit()
        await db.refresh(bag)
        
        await invalidate_cache(f"bag:{bag_id}")
        return bag
    
    async def return_bag(
        self,
        db: AsyncSession,
        bag_id: int,
        operator_id: int,
        current_user: User,
        notes: Optional[str] = None
    ) -> Bag:
        """Возврат сумки на склад"""
        bag = await db.execute(
            select(Bag)
            .where(Bag.id == bag_id)
            .options(selectinload(Bag.items))
        )
        bag = bag.scalar_one_or_none()
        
        if not bag:
            raise NotFoundError(f"Сумка {bag_id} не найдена")
        
        if bag.issued_to_id != operator_id:
            raise PermissionError("Сумка выдана другому оператору")
        
        bag.status = 'returned'
        bag.returned_at = datetime.now(timezone.utc)
        bag.return_notes = notes
        
        # Обновление статусов бункеров
        for item in bag.items:
            if item.item_type == 'bunker' and item.bunker:
                item.bunker.status = 'empty' if item.is_empty else 'filled'
                item.bunker.current_bag_id = None
                item.bunker.use_cycles += 1
        
        await db.commit()
        await db.refresh(bag)
        
        await invalidate_cache(f"bag:{bag_id}")
        await invalidate_cache(f"operator:{operator_id}:bags")
        
        return bag
    
    async def get_operator_bags(
        self,
        db: AsyncSession,
        operator_id: int,
        status: Optional[str] = None
    ) -> List[Bag]:
        """Получить сумки оператора"""
        query = select(Bag).where(Bag.issued_to_id == operator_id)
        
        if status:
            query = query.where(Bag.status == status)
        
        query = query.options(
            selectinload(Bag.task),
            selectinload(Bag.items)
        ).order_by(Bag.issued_at.desc())
        
        result = await db.execute(query)
        return result.scalars().all()
    
    @cache_result(expire=300)
    async def get_bag_statistics(
        self,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Статистика по сумкам"""
        # Количество по статусам
        status_counts = await db.execute(
            select(
                Bag.status,
                func.count(Bag.id).label('count')
            ).group_by(Bag.status)
        )
        
        # Среднее время подготовки
        avg_prep_time = await db.execute(
            select(
                func.avg(
                    func.extract('epoch', Bag.prepared_at - Bag.created_at)
                ).label('avg_seconds')
            ).where(
                and_(
                    Bag.prepared_at.isnot(None),
                    Bag.status != 'preparing'
                )
            )
        )
        
        # Процент полных проверок
        complete_checks = await db.execute(
            select(
                func.count(Bag.id).filter(Bag.is_complete == True).label('complete'),
                func.count(Bag.id).label('total')
            ).where(Bag.status.in_(['checked', 'returned']))
        )
        
        result = complete_checks.one()
        completeness_rate = (result.complete / result.total * 100) if result.total > 0 else 0
        
        return {
            'status_distribution': {
                row.status: row.count 
                for row in status_counts
            },
            'average_preparation_time': avg_prep_time.scalar() or 0,
            'completeness_rate': round(completeness_rate, 2),
            'total_bags': await db.scalar(
                select(func.count(Bag.id))
            )
        }
    
    async def get_bag_contents(
        self,
        db: AsyncSession,
        bag_id: int
    ) -> Dict[str, Any]:
        """Детальное содержимое сумки"""
        bag = await db.execute(
            select(Bag)
            .where(Bag.id == bag_id)
            .options(
                selectinload(Bag.items).selectinload(BagItem.bunker),
                selectinload(Bag.items).selectinload(BagItem.ingredient),
                selectinload(Bag.task).selectinload(MachineTask.machine)
            )
        )
        bag = bag.scalar_one_or_none()
        
        if not bag:
            raise NotFoundError(f"Сумка {bag_id} не найдена")
        
        contents = {
            'bag_id': bag.id,
            'status': bag.status,
            'task': {
                'id': bag.task.id,
                'type': bag.task.task_type,
                'machine': bag.task.machine.name
            } if bag.task else None,
            'items': []
        }
        
        for item in bag.items:
            item_data = {
                'id': item.id,
                'type': item.item_type,
                'quantity': item.quantity,
                'is_missing': item.is_missing,
                'is_empty': item.is_empty
            }
            
            if item.item_type == 'bunker' and item.bunker:
                item_data['bunker'] = {
                    'code': item.bunker.code,
                    'status': item.bunker.status,
                    'ingredient': item.bunker.current_ingredient.name 
                        if item.bunker.current_ingredient else None
                }
            elif item.item_type == 'ingredient' and item.ingredient:
                item_data['ingredient'] = {
                    'name': item.ingredient.name,
                    'unit': item.ingredient.unit
                }
            
            contents['items'].append(item_data)
        
        return contents