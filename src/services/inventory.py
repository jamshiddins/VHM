from typing import List, Optional, Dict, Any
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models.inventory import (
    Inventory, Ingredient, Warehouse, LocationType,
    IngredientCategory, IngredientUnit
)
from src.db.models.machine import Machine
from src.db.models.route import MachineTask
from src.core.exceptions import (
    IngredientNotFound, InsufficientStock, InventoryException
)


class InventoryService:
    """Сервис для работы с остатками"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    # === Работа с ингредиентами ===
    
    async def get_ingredient_by_id(self, ingredient_id: int) -> Optional[Ingredient]:
        """Получение ингредиента по ID"""
        return await self.session.get(Ingredient, ingredient_id)
    
    async def get_ingredient_by_code(self, code: str) -> Optional[Ingredient]:
        """Получение ингредиента по коду"""
        query = select(Ingredient).where(Ingredient.code == code.upper())
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def create_ingredient(
        self,
        code: str,
        name: str,
        category: IngredientCategory,
        unit: IngredientUnit,
        cost_per_unit: Optional[Decimal] = None,
        min_stock_level: Optional[Decimal] = None,
        barcode: Optional[str] = None
    ) -> Ingredient:
        """Создание нового ингредиента"""
        ingredient = Ingredient(
            code=code.upper(),
            name=name,
            category=category,
            unit=unit,
            cost_per_unit=cost_per_unit,
            min_stock_level=min_stock_level,
            barcode=barcode
        )
        
        self.session.add(ingredient)
        await self.session.commit()
        await self.session.refresh(ingredient)
        
        return ingredient
    
    async def get_ingredients_list(
        self,
        category: Optional[IngredientCategory] = None,
        search: Optional[str] = None,
        only_critical: bool = False
    ) -> List[Ingredient]:
        """Получение списка ингредиентов"""
        query = select(Ingredient)
        
        if category:
            query = query.where(Ingredient.category == category)
        
        if search:
            search_term = f"%{search}%"
            query = query.where(
                or_(
                    Ingredient.code.ilike(search_term),
                    Ingredient.name.ilike(search_term),
                    Ingredient.barcode.ilike(search_term)
                )
            )
        
        if only_critical:
            # TODO: Добавить фильтр по критическим остаткам
            pass
        
        result = await self.session.execute(query.order_by(Ingredient.name))
        return list(result.scalars().all())
    
    # === Работа с остатками ===
    
    async def get_current_stock(
        self,
        location_type: LocationType,
        location_id: int,
        ingredient_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Получение текущих остатков для локации"""
        # Подзапрос для получения последней записи по каждому ингредиенту
        subquery = select(
            Inventory.ingredient_id,
            func.max(Inventory.action_timestamp).label('max_timestamp')
        ).where(
            and_(
                Inventory.location_type == location_type,
                Inventory.location_id == location_id
            )
        )
        
        if ingredient_id:
            subquery = subquery.where(Inventory.ingredient_id == ingredient_id)
        
        subquery = subquery.group_by(Inventory.ingredient_id).subquery()
        
        # Основной запрос
        query = select(Inventory).join(
            subquery,
            and_(
                Inventory.ingredient_id == subquery.c.ingredient_id,
                Inventory.action_timestamp == subquery.c.max_timestamp,
                Inventory.location_type == location_type,
                Inventory.location_id == location_id
            )
        ).options(selectinload(Inventory.ingredient))
        
        result = await self.session.execute(query)
        inventory_items = result.scalars().all()
        
        # Форматируем результат
        stock_data = []
        for item in inventory_items:
            stock_data.append({
                'ingredient_id': item.ingredient_id,
                'ingredient_name': item.ingredient.name,
                'ingredient_code': item.ingredient.code,
                'quantity': float(item.quantity),
                'unit': item.ingredient.unit.value,
                'batch_number': item.batch_number,
                'expiry_date': item.expiry_date,
                'last_updated': item.action_timestamp
            })
        
        return stock_data
    
    async def get_warehouse_inventory_by_category(
        self,
        category: str,
        warehouse_id: int = 1  # Основной склад по умолчанию
    ) -> List[Dict[str, Any]]:
        """Получение остатков на складе по категории"""
        # Получаем текущие остатки
        current_stock = await self.get_current_stock(
            LocationType.WAREHOUSE,
            warehouse_id
        )
        
        # Фильтруем по категории
        filtered_stock = []
        for item in current_stock:
            ingredient = await self.get_ingredient_by_id(item['ingredient_id'])
            if ingredient and ingredient.category.value == category:
                filtered_stock.append({
                    **item,
                    'min_stock': float(ingredient.min_stock_level or 0),
                    'cost_per_unit': float(ingredient.cost_per_unit or 0)
                })
        
        return filtered_stock
    
    async def get_inventory_summary(self) -> Dict[str, Any]:
        """Получение сводки по остаткам"""
        # Получаем все текущие остатки основного склада
        warehouse_stock = await self.get_current_stock(
            LocationType.WAREHOUSE,
            1  # Основной склад
        )
        
        total_items = len(warehouse_stock)
        total_value = 0
        by_category = {}
        critical_items = []
        
        for item in warehouse_stock:
            ingredient = await self.get_ingredient_by_id(item['ingredient_id'])
            if not ingredient:
                continue
            
            # Подсчет стоимости
            item_value = item['quantity'] * float(ingredient.cost_per_unit or 0)
            total_value += item_value
            
            # Группировка по категориям
            category = ingredient.category.value
            if category not in by_category:
                by_category[category] = {'count': 0, 'value': 0}
            
            by_category[category]['count'] += 1
            by_category[category]['value'] += item_value
            
            # Проверка критических остатков
            if ingredient.min_stock_level and item['quantity'] < float(ingredient.min_stock_level):
                critical_items.append({
                    'id': ingredient.id,
                    'name': ingredient.name,
                    'quantity': item['quantity'],
                    'min_stock': float(ingredient.min_stock_level),
                    'unit': ingredient.unit.value
                })
        
        return {
            'total_items': total_items,
            'total_value': total_value,
            'by_category': by_category,
            'critical_items': sorted(
                critical_items, 
                key=lambda x: x['quantity'] / x['min_stock']
            )[:10]  # Топ-10 критических
        }
    
    # === Операции с остатками ===
    
    async def create_inventory_record(
        self,
        ingredient_id: int,
        location_type: LocationType,
        location_id: int,
        quantity: Decimal,
        created_by_id: int,
        batch_number: Optional[str] = None,
        expiry_date: Optional[date] = None,
        notes: Optional[str] = None,
        action_timestamp: Optional[datetime] = None
    ) -> Inventory:
        """Создание записи об остатке"""
        inventory = Inventory(
            ingredient_id=ingredient_id,
            location_type=location_type,
            location_id=location_id,
            quantity=quantity,
            batch_number=batch_number,
            expiry_date=expiry_date,
            created_by_id=created_by_id,
            notes=notes,
            action_timestamp=action_timestamp or datetime.utcnow()
        )
        
        self.session.add(inventory)
        await self.session.commit()
        
        return inventory
    
    async def transfer_inventory(
        self,
        ingredient_id: int,
        from_location_type: LocationType,
        from_location_id: int,
        to_location_type: LocationType,
        to_location_id: int,
        quantity: Decimal,
        transferred_by_id: int,
        notes: Optional[str] = None
    ) -> tuple[Inventory, Inventory]:
        """Перемещение товара между локациями"""
        # Проверяем наличие на складе-источнике
        current_stock = await self.get_current_stock(
            from_location_type,
            from_location_id,
            ingredient_id
        )
        
        if not current_stock:
            raise InsufficientStock("Товар не найден на складе-источнике")
        
        available_quantity = current_stock[0]['quantity']
        if available_quantity < float(quantity):
            raise InsufficientStock(
                f"Недостаточно товара. Доступно: {available_quantity}, "
                f"запрошено: {quantity}"
            )
        
        # Создаем записи о перемещении
        timestamp = datetime.utcnow()
        
        # Уменьшаем на складе-источнике
        from_record = await self.create_inventory_record(
            ingredient_id=ingredient_id,
            location_type=from_location_type,
            location_id=from_location_id,
            quantity=Decimal(str(available_quantity - float(quantity))),
            created_by_id=transferred_by_id,
            notes=f"Перемещение: {notes}" if notes else "Перемещение",
            action_timestamp=timestamp
        )
        
        # Увеличиваем на складе-приемнике
        to_current = await self.get_current_stock(
            to_location_type,
            to_location_id,
            ingredient_id
        )
        
        to_quantity = Decimal(str(to_current[0]['quantity'])) if to_current else Decimal('0')
        
        to_record = await self.create_inventory_record(
            ingredient_id=ingredient_id,
            location_type=to_location_type,
            location_id=to_location_id,
            quantity=to_quantity + quantity,
            created_by_id=transferred_by_id,
            notes=f"Получено: {notes}" if notes else "Получено",
            action_timestamp=timestamp
        )
        
        await self.session.commit()
        
        return from_record, to_record
    
    async def issue_from_warehouse(
        self,
        ingredient_id: int,
        quantity: Decimal,
        issued_by: int,
        issued_to_task_id: Optional[int] = None,
        notes: Optional[str] = None
    ) -> Inventory:
        """Выдача со склада"""
        # Если указана задача, перемещаем в сумку задачи
        if issued_to_task_id:
            _, to_record = await self.transfer_inventory(
                ingredient_id=ingredient_id,
                from_location_type=LocationType.WAREHOUSE,
                from_location_id=1,  # Основной склад
                to_location_type=LocationType.BAG,
                to_location_id=issued_to_task_id,
                quantity=quantity,
                transferred_by_id=issued_by,
                notes=notes
            )
            return to_record
        else:
            # Просто уменьшаем остаток на складе
            current = await self.get_current_stock(
                LocationType.WAREHOUSE,
                1,
                ingredient_id
            )
            
            if not current:
                raise InsufficientStock("Товар не найден на складе")
            
            new_quantity = Decimal(str(current[0]['quantity'])) - quantity
            if new_quantity < 0:
                raise InsufficientStock("Недостаточно товара на складе")
            
            return await self.create_inventory_record(
                ingredient_id=ingredient_id,
                location_type=LocationType.WAREHOUSE,
                location_id=1,
                quantity=new_quantity,
                created_by_id=issued_by,
                notes=notes or "Выдано со склада"
            )
    
    async def receive_to_warehouse(
        self,
        ingredient_id: int,
        quantity: Decimal,
        batch_number: Optional[str] = None,
        expiry_date: Optional[date] = None,
        received_by: int = None,
        notes: Optional[str] = None
    ) -> Inventory:
        """Приемка на склад"""
        # Получаем текущий остаток
        current = await self.get_current_stock(
            LocationType.WAREHOUSE,
            1,
            ingredient_id
        )
        
        current_quantity = Decimal(str(current[0]['quantity'])) if current else Decimal('0')
        
        return await self.create_inventory_record(
            ingredient_id=ingredient_id,
            location_type=LocationType.WAREHOUSE,
            location_id=1,
            quantity=current_quantity + quantity,
            batch_number=batch_number,
            expiry_date=expiry_date,
            created_by_id=received_by,
            notes=notes or "Поступление на склад"
        )
    
    async def record_weighing(
        self,
        ingredient_id: int,
        weight: Decimal,
        operator_id: int,
        machine_id: Optional[int] = None,
        batch_number: Optional[str] = None
    ) -> Dict[str, Any]:
        """Запись взвешивания (возврат от оператора)"""
        # Создаем запись о возврате на склад
        inventory = await self.receive_to_warehouse(
            ingredient_id=ingredient_id,
            quantity=weight,
            batch_number=batch_number,
            received_by=operator_id,
            notes=f"Возврат после взвешивания"
        )
        
        # Получаем информацию для ответа
        ingredient = await self.get_ingredient_by_id(ingredient_id)
        
        return {
            'id': inventory.id,
            'ingredient_name': ingredient.name,
            'quantity': float(weight),
            'unit': ingredient.unit.value,
            'operator_id': operator_id,
            'timestamp': inventory.action_timestamp
        }
    
    async def get_recent_weighings(
        self,
        limit: int = 10,
        operator_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Получение истории взвешиваний"""
        query = select(Inventory).options(
            selectinload(Inventory.ingredient),
            selectinload(Inventory.created_by)
        ).where(
            and_(
                Inventory.location_type == LocationType.WAREHOUSE,
                Inventory.notes.like('%взвешивани%')
            )
        )
        
        if operator_id:
            query = query.where(Inventory.created_by_id == operator_id)
        
        query = query.order_by(desc(Inventory.action_timestamp)).limit(limit)
        
        result = await self.session.execute(query)
        weighings = result.scalars().all()
        
        return [
            {
                'id': w.id,
                'ingredient_name': w.ingredient.name,
                'quantity': float(w.quantity),
                'unit': w.ingredient.unit.value,
                'operator_name': w.created_by.full_name if w.created_by else 'Неизвестно',
                'timestamp': w.action_timestamp,
                'batch_number': w.batch_number
            }
            for w in weighings
        ]
    
    async def get_inventory_movements(
        self,
        location_type: Optional[LocationType] = None,
        location_id: Optional[int] = None,
        ingredient_id: Optional[int] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Inventory]:
        """Получение движений товаров"""
        query = select(Inventory).options(
            selectinload(Inventory.ingredient),
            selectinload(Inventory.created_by)
        )
        
        conditions = []
        
        if location_type:
            conditions.append(Inventory.location_type == location_type)
        
        if location_id:
            conditions.append(Inventory.location_id == location_id)
        
        if ingredient_id:
            conditions.append(Inventory.ingredient_id == ingredient_id)
        
        if date_from:
            conditions.append(Inventory.action_timestamp >= date_from)
        
        if date_to:
            conditions.append(Inventory.action_timestamp <= date_to)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(desc(Inventory.action_timestamp)).limit(limit)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def check_expiring_items(
        self,
        days_ahead: int = 7
    ) -> List[Dict[str, Any]]:
        """Проверка товаров с истекающим сроком годности"""
        expiry_date = date.today() + timedelta(days=days_ahead)
        
        # Получаем последние записи с датой годности
        query = select(Inventory).options(
            selectinload(Inventory.ingredient)
        ).where(
            and_(
                Inventory.expiry_date.isnot(None),
                Inventory.expiry_date <= expiry_date,
                Inventory.quantity > 0
            )
        ).order_by(Inventory.expiry_date)
        
        result = await self.session.execute(query)
        items = result.scalars().all()
        
        expiring = []
        for item in items:
            # Проверяем, что это актуальный остаток
            current = await self.get_current_stock(
                item.location_type,
                item.location_id,
                item.ingredient_id
            )
            
            if current and current[0]['expiry_date'] == item.expiry_date:
                days_left = (item.expiry_date - date.today()).days
                expiring.append({
                    'ingredient_name': item.ingredient.name,
                    'quantity': float(item.quantity),
                    'unit': item.ingredient.unit.value,
                    'expiry_date': item.expiry_date,
                    'days_left': days_left,
                    'location_type': item.location_type.value,
                    'location_id': item.location_id,
                    'batch_number': item.batch_number
                })
        
        return sorted(expiring, key=lambda x: x['days_left'])