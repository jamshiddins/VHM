# src/services/supplier_service.py

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..db.models import (
    Supplier, Purchase, PurchaseItem, SupplierIngredient,
    Ingredient, Inventory, User
)
from ..db.schemas import (
    SupplierCreate, SupplierUpdate, PurchaseCreate,
    PurchaseItemCreate, SupplierIngredientCreate
)
from ..core.exceptions import NotFoundError, ValidationError
from ..utils.cache import cache_result, invalidate_cache
from .base import BaseService


class SupplierService(BaseService[Supplier, SupplierCreate, SupplierUpdate]):
    """Сервис для управления поставщиками и закупками"""
    
    model = Supplier
    
    async def create_supplier(
        self,
        db: AsyncSession,
        supplier_data: SupplierCreate,
        current_user: User
    ) -> Supplier:
        """Создание нового поставщика"""
        # Проверка уникальности ИНН
        if supplier_data.inn:
            existing = await db.execute(
                select(Supplier).where(Supplier.inn == supplier_data.inn)
            )
            if existing.scalar_one_or_none():
                raise ValidationError(f"Поставщик с ИНН {supplier_data.inn} уже существует")
        
        supplier = Supplier(
            **supplier_data.model_dump(),
            created_by_id=current_user.id
        )
        db.add(supplier)
        await db.commit()
        await db.refresh(supplier)
        
        await invalidate_cache("suppliers:*")
        return supplier
    
    async def add_supplier_ingredients(
        self,
        db: AsyncSession,
        supplier_id: int,
        ingredients: List[SupplierIngredientCreate]
    ) -> List[SupplierIngredient]:
        """Добавление ингредиентов поставщика"""
        supplier = await self.get(db, supplier_id)
        if not supplier:
            raise NotFoundError(f"Поставщик {supplier_id} не найден")
        
        created_items = []
        
        for ing_data in ingredients:
            # Проверка существования ингредиента
            ingredient = await db.get(Ingredient, ing_data.ingredient_id)
            if not ingredient:
                raise NotFoundError(f"Ингредиент {ing_data.ingredient_id} не найден")
            
            # Проверка дубликатов
            existing = await db.execute(
                select(SupplierIngredient).where(
                    and_(
                        SupplierIngredient.supplier_id == supplier_id,
                        SupplierIngredient.ingredient_id == ing_data.ingredient_id
                    )
                )
            )
            if existing.scalar_one_or_none():
                continue  # Пропускаем дубликаты
            
            supplier_ing = SupplierIngredient(
                supplier_id=supplier_id,
                **ing_data.model_dump()
            )
            db.add(supplier_ing)
            created_items.append(supplier_ing)
        
        await db.commit()
        
        await invalidate_cache(f"supplier:{supplier_id}:ingredients")
        return created_items
    
    async def create_purchase(
        self,
        db: AsyncSession,
        purchase_data: PurchaseCreate,
        items: List[PurchaseItemCreate],
        current_user: User
    ) -> Purchase:
        """Создание закупки с позициями"""
        supplier = await self.get(db, purchase_data.supplier_id)
        if not supplier:
            raise NotFoundError(f"Поставщик {purchase_data.supplier_id} не найден")
        
        # Создание закупки
        purchase = Purchase(
            **purchase_data.model_dump(exclude={'items'}),
            created_by_id=current_user.id,
            status='draft'
        )
        db.add(purchase)
        await db.flush()
        
        # Добавление позиций
        total_amount = Decimal('0')
        
        for item_data in items:
            # Проверка ингредиента
            ingredient = await db.get(Ingredient, item_data.ingredient_id)
            if not ingredient:
                raise NotFoundError(f"Ингредиент {item_data.ingredient_id} не найден")
            
            # Расчет суммы позиции
            amount = item_data.quantity * item_data.price_per_unit
            
            purchase_item = PurchaseItem(
                purchase_id=purchase.id,
                **item_data.model_dump(),
                amount=amount
            )
            db.add(purchase_item)
            total_amount += amount
        
        # Обновление общей суммы
        purchase.total_amount = total_amount
        
        await db.commit()
        await db.refresh(purchase)
        
        await invalidate_cache("purchases:*")
        return purchase
    
    async def confirm_purchase(
        self,
        db: AsyncSession,
        purchase_id: int,
        current_user: User
    ) -> Purchase:
        """Подтверждение закупки"""
        purchase = await db.execute(
            select(Purchase)
            .where(Purchase.id == purchase_id)
            .options(selectinload(Purchase.items))
        )
        purchase = purchase.scalar_one_or_none()
        
        if not purchase:
            raise NotFoundError(f"Закупка {purchase_id} не найдена")
        
        if purchase.status != 'draft':
            raise ValidationError("Можно подтвердить только черновик закупки")
        
        purchase.status = 'confirmed'
        purchase.confirmed_at = datetime.now(timezone.utc)
        purchase.confirmed_by_id = current_user.id
        
        await db.commit()
        await db.refresh(purchase)
        
        await invalidate_cache(f"purchase:{purchase_id}")
        return purchase
    
    async def receive_purchase(
        self,
        db: AsyncSession,
        purchase_id: int,
        received_items: Dict[int, Dict[str, Any]],
        current_user: User
    ) -> Purchase:
        """Приемка закупки на склад"""
        purchase = await db.execute(
            select(Purchase)
            .where(Purchase.id == purchase_id)
            .options(selectinload(Purchase.items))
        )
        purchase = purchase.scalar_one_or_none()
        
        if not purchase:
            raise NotFoundError(f"Закупка {purchase_id} не найдена")
        
        if purchase.status != 'confirmed':
            raise ValidationError("Можно принять только подтвержденную закупку")
        
        # Обработка каждой позиции
        for item in purchase.items:
            if item.id in received_items:
                received_data = received_items[item.id]
                actual_quantity = received_data.get('quantity', item.quantity)
                
                # Обновление фактического количества
                item.actual_quantity = actual_quantity
                
                # Создание записи в инвентаре
                inventory = Inventory(
                    ingredient_id=item.ingredient_id,
                    location_type='warehouse',
                    location_id=1,  # Основной склад
                    quantity=actual_quantity,
                    operation_type='purchase',
                    reference_type='purchase',
                    reference_id=purchase.id,
                    action_timestamp=datetime.now(timezone.utc),
                    created_by_id=current_user.id,
                    notes=f"Приемка закупки #{purchase.id}"
                )
                db.add(inventory)
        
        purchase.status = 'received'
        purchase.received_at = datetime.now(timezone.utc)
        purchase.received_by_id = current_user.id
        
        await db.commit()
        await db.refresh(purchase)
        
        await invalidate_cache(f"purchase:{purchase_id}")
        await invalidate_cache("inventory:warehouse:*")
        
        return purchase
    
    async def get_supplier_statistics(
        self,
        db: AsyncSession,
        supplier_id: int
    ) -> Dict[str, Any]:
        """Статистика по поставщику"""
        supplier = await self.get(db, supplier_id)
        if not supplier:
            raise NotFoundError(f"Поставщик {supplier_id} не найден")
        
        # Общая статистика закупок
        purchase_stats = await db.execute(
            select(
                func.count(Purchase.id).label('total_purchases'),
                func.sum(Purchase.total_amount).label('total_amount'),
                func.avg(Purchase.total_amount).label('avg_amount')
            ).where(Purchase.supplier_id == supplier_id)
        )
        stats = purchase_stats.one()
        
        # Статистика по статусам
        status_counts = await db.execute(
            select(
                Purchase.status,
                func.count(Purchase.id).label('count')
            ).where(Purchase.supplier_id == supplier_id)
            .group_by(Purchase.status)
        )
        
        # Топ ингредиентов
        top_ingredients = await db.execute(
            select(
                PurchaseItem.ingredient_id,
                Ingredient.name,
                func.sum(PurchaseItem.quantity).label('total_quantity'),
                func.sum(PurchaseItem.amount).label('total_amount')
            ).join(Purchase)
            .join(Ingredient, PurchaseItem.ingredient_id == Ingredient.id)
            .where(Purchase.supplier_id == supplier_id)
            .group_by(PurchaseItem.ingredient_id, Ingredient.name)
            .order_by(func.sum(PurchaseItem.amount).desc())
            .limit(10)
        )
        
        # Динамика закупок по месяцам
        monthly_dynamics = await db.execute(
            select(
                func.date_trunc('month', Purchase.created_at).label('month'),
                func.count(Purchase.id).label('count'),
                func.sum(Purchase.total_amount).label('amount')
            ).where(
                and_(
                    Purchase.supplier_id == supplier_id,
                    Purchase.created_at >= datetime.now() - timedelta(days=365)
                )
            ).group_by(func.date_trunc('month', Purchase.created_at))
            .order_by(func.date_trunc('month', Purchase.created_at))
        )
        
        return {
            'total_purchases': stats.total_purchases or 0,
            'total_amount': float(stats.total_amount or 0),
            'average_amount': float(stats.avg_amount or 0),
            'status_distribution': {
                row.status: row.count 
                for row in status_counts
            },
            'top_ingredients': [
                {
                    'ingredient_id': row.ingredient_id,
                    'name': row.name,
                    'total_quantity': float(row.total_quantity),
                    'total_amount': float(row.total_amount)
                }
                for row in top_ingredients
            ],
            'monthly_dynamics': [
                {
                    'month': row.month.isoformat(),
                    'count': row.count,
                    'amount': float(row.amount)
                }
                for row in monthly_dynamics
            ]
        }
    
    @cache_result(expire=300)
    async def find_best_supplier_for_ingredient(
        self,
        db: AsyncSession,
        ingredient_id: int
    ) -> Optional[Dict[str, Any]]:
        """Найти лучшего поставщика для ингредиента"""
        # Поставщики с этим ингредиентом
        suppliers = await db.execute(
            select(
                SupplierIngredient,
                Supplier
            ).join(Supplier)
            .where(
                and_(
                    SupplierIngredient.ingredient_id == ingredient_id,
                    Supplier.is_active == True
                )
            )
        )
        
        best_supplier = None
        best_price = None
        
        for supp_ing, supplier in suppliers:
            # Средняя цена по последним закупкам
            avg_price = await db.execute(
                select(func.avg(PurchaseItem.price_per_unit))
                .join(Purchase)
                .where(
                    and_(
                        Purchase.supplier_id == supplier.id,
                        PurchaseItem.ingredient_id == ingredient_id,
                        Purchase.status == 'received',
                        Purchase.created_at >= datetime.now() - timedelta(days=90)
                    )
                )
            )
            price = avg_price.scalar()
            
            if price and (best_price is None or price < best_price):
                best_price = price
                best_supplier = {
                    'supplier_id': supplier.id,
                    'supplier_name': supplier.name,
                    'average_price': float(price),
                    'supplier_price': float(supp_ing.price) if supp_ing.price else None,
                    'min_order_quantity': float(supp_ing.min_order_quantity) 
                        if supp_ing.min_order_quantity else None
                }
        
        return best_supplier
    
    async def get_purchases_calendar(
        self,
        db: AsyncSession,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Календарь закупок"""
        purchases = await db.execute(
            select(Purchase)
            .where(
                and_(
                    Purchase.delivery_date >= start_date,
                    Purchase.delivery_date <= end_date
                )
            ).options(
                selectinload(Purchase.supplier),
                selectinload(Purchase.items)
            ).order_by(Purchase.delivery_date)
        )
        
        calendar = []
        for purchase in purchases.scalars():
            calendar.append({
                'id': purchase.id,
                'date': purchase.delivery_date.isoformat(),
                'supplier': purchase.supplier.name,
                'status': purchase.status,
                'total_amount': float(purchase.total_amount),
                'items_count': len(purchase.items)
            })
        
        return calendar