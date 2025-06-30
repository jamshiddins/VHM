# src/services/cash_collection_service.py

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..db.models import (
    CashCollection, CashDenomination, Machine, User, 
    FinanceAccount, FinanceTransaction, Sale
)
from ..db.schemas import (
    CashCollectionCreate, CashDenominationCreate,
    CashCollectionUpdate
)
from ..core.exceptions import NotFoundError, ValidationError, PermissionError
from ..utils.cache import cache_result, invalidate_cache
from .base import BaseService


class CashCollectionService(BaseService[CashCollection, CashCollectionCreate, CashCollectionUpdate]):
    """Сервис для управления инкассацией"""
    
    model = CashCollection
    
    async def start_collection(
        self,
        db: AsyncSession,
        machine_id: int,
        operator_id: int,
        before_photo_url: str
    ) -> CashCollection:
        """Начало инкассации"""
        # Проверка автомата
        machine = await db.get(Machine, machine_id)
        if not machine:
            raise NotFoundError(f"Автомат {machine_id} не найден")
        
        # Проверка незавершенной инкассации
        existing = await db.execute(
            select(CashCollection).where(
                and_(
                    CashCollection.machine_id == machine_id,
                    CashCollection.status == 'in_progress'
                )
            )
        )
        if existing.scalar_one_or_none():
            raise ValidationError("У этого автомата уже есть незавершенная инкассация")
        
        # Создание записи инкассации
        collection = CashCollection(
            machine_id=machine_id,
            operator_id=operator_id,
            status='in_progress',
            before_photo_url=before_photo_url,
            collected_at=datetime.now(timezone.utc)
        )
        
        db.add(collection)
        await db.commit()
        await db.refresh(collection)
        
        await invalidate_cache(f"machine:{machine_id}:collections")
        return collection
    
    async def add_denominations(
        self,
        db: AsyncSession,
        collection_id: int,
        denominations: List[CashDenominationCreate],
        operator_id: int
    ) -> CashCollection:
        """Добавление купюр по номиналам"""
        collection = await self.get(db, collection_id)
        if not collection:
            raise NotFoundError(f"Инкассация {collection_id} не найдена")
        
        if collection.operator_id != operator_id:
            raise PermissionError("Вы не можете редактировать чужую инкассацию")
        
        if collection.status != 'in_progress':
            raise ValidationError("Инкассация уже завершена")
        
        # Удаление старых записей (если редактируют)
        await db.execute(
            select(CashDenomination).where(
                CashDenomination.collection_id == collection_id
            ).delete()
        )
        
        # Добавление новых
        total_amount = Decimal('0')
        
        for denom_data in denominations:
            amount = denom_data.denomination * denom_data.quantity
            
            denomination = CashDenomination(
                collection_id=collection_id,
                denomination=denom_data.denomination,
                quantity=denom_data.quantity,
                amount=amount
            )
            db.add(denomination)
            total_amount += amount
        
        # Обновление общей суммы
        collection.amount_collected = total_amount
        
        await db.commit()
        await db.refresh(collection)
        
        await invalidate_cache(f"collection:{collection_id}")
        return collection
    
    async def complete_collection(
        self,
        db: AsyncSession,
        collection_id: int,
        operator_id: int,
        after_photo_url: str,
        notes: Optional[str] = None
    ) -> CashCollection:
        """Завершение инкассации"""
        collection = await db.execute(
            select(CashCollection)
            .where(CashCollection.id == collection_id)
            .options(selectinload(CashCollection.denominations))
        )
        collection = collection.scalar_one_or_none()
        
        if not collection:
            raise NotFoundError(f"Инкассация {collection_id} не найдена")
        
        if collection.operator_id != operator_id:
            raise PermissionError("Вы не можете завершить чужую инкассацию")
        
        if collection.status != 'in_progress':
            raise ValidationError("Инкассация уже завершена")
        
        if not collection.denominations:
            raise ValidationError("Необходимо указать собранные купюры")
        
        # Расчет продаж с последней инкассации
        last_collection = await db.execute(
            select(CashCollection)
            .where(
                and_(
                    CashCollection.machine_id == collection.machine_id,
                    CashCollection.id != collection_id,
                    CashCollection.status == 'verified'
                )
            ).order_by(CashCollection.collected_at.desc())
            .limit(1)
        )
        last = last_collection.scalar_one_or_none()
        
        # Подсчет продаж
        sales_query = select(
            func.coalesce(func.sum(Sale.amount), 0)
        ).where(
            Sale.machine_id == collection.machine_id
        )
        
        if last:
            sales_query = sales_query.where(
                Sale.sale_date > last.collected_at
            )
        
        expected_amount = await db.scalar(sales_query)
        
        # Расчет расхождения
        collection.expected_amount = expected_amount
        collection.discrepancy = collection.amount_collected - expected_amount
        collection.after_photo_url = after_photo_url
        collection.notes = notes
        collection.status = 'completed'
        collection.completed_at = datetime.now(timezone.utc)
        
        await db.commit()
        await db.refresh(collection)
        
        await invalidate_cache(f"collection:{collection_id}")
        await invalidate_cache(f"machine:{collection.machine_id}:collections")
        
        return collection
    
    async def verify_collection(
        self,
        db: AsyncSession,
        collection_id: int,
        verifier_id: int,
        is_approved: bool,
        verification_notes: Optional[str] = None
    ) -> CashCollection:
        """Проверка инкассации менеджером"""
        collection = await self.get(db, collection_id)
        if not collection:
            raise NotFoundError(f"Инкассация {collection_id} не найдена")
        
        if collection.status != 'completed':
            raise ValidationError("Можно проверить только завершенную инкассацию")
        
        collection.verified_by_id = verifier_id
        collection.verified_at = datetime.now(timezone.utc)
        collection.verification_notes = verification_notes
        
        if is_approved:
            collection.status = 'verified'
            
            # Создание финансовой транзакции
            machine_account = await db.execute(
                select(FinanceAccount).where(
                    and_(
                        FinanceAccount.account_type == 'machine',
                        FinanceAccount.reference_id == collection.machine_id
                    )
                )
            )
            machine_acc = machine_account.scalar_one_or_none()
            
            if machine_acc:
                # Перевод с автомата на основной счет
                transaction = FinanceTransaction(
                    account_id=machine_acc.id,
                    transaction_type='transfer',
                    transaction_date=datetime.now(timezone.utc),
                    amount=-collection.amount_collected,  # Списание
                    reference_type='cash_collection',
                    reference_id=collection.id,
                    description=f"Инкассация автомата {collection.machine.code}",
                    created_by_id=verifier_id
                )
                db.add(transaction)
                
                # Зачисление на основной счет
                main_account = await db.execute(
                    select(FinanceAccount).where(
                        FinanceAccount.name == 'Основной счет'
                    )
                )
                main_acc = main_account.scalar_one_or_none()
                
                if main_acc:
                    credit_transaction = FinanceTransaction(
                        account_id=main_acc.id,
                        transaction_type='transfer',
                        transaction_date=datetime.now(timezone.utc),
                        amount=collection.amount_collected,  # Зачисление
                        reference_type='cash_collection',
                        reference_id=collection.id,
                        description=f"Инкассация автомата {collection.machine.code}",
                        created_by_id=verifier_id
                    )
                    db.add(credit_transaction)
        else:
            collection.status = 'rejected'
        
        await db.commit()
        await db.refresh(collection)
        
        await invalidate_cache(f"collection:{collection_id}")
        return collection
    
    async def get_machine_collections(
        self,
        db: AsyncSession,
        machine_id: int,
        limit: int = 50
    ) -> List[CashCollection]:
        """История инкассаций автомата"""
        result = await db.execute(
            select(CashCollection)
            .where(CashCollection.machine_id == machine_id)
            .options(
                selectinload(CashCollection.operator),
                selectinload(CashCollection.verified_by),
                selectinload(CashCollection.denominations)
            )
            .order_by(CashCollection.collected_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_operator_collections(
        self,
        db: AsyncSession,
        operator_id: int,
        status: Optional[str] = None,
        date_from: Optional[datetime] = None
    ) -> List[CashCollection]:
        """Инкассации оператора"""
        query = select(CashCollection).where(
            CashCollection.operator_id == operator_id
        )
        
        if status:
            query = query.where(CashCollection.status == status)
        
        if date_from:
            query = query.where(CashCollection.collected_at >= date_from)
        
        query = query.options(
            selectinload(CashCollection.machine),
            selectinload(CashCollection.denominations)
        ).order_by(CashCollection.collected_at.desc())
        
        result = await db.execute(query)
        return result.scalars().all()
    
    @cache_result(expire=300)
    async def get_collection_statistics(
        self,
        db: AsyncSession,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Статистика инкассаций"""
        query = select(CashCollection).where(
            CashCollection.status.in_(['verified', 'completed'])
        )
        
        if date_from:
            query = query.where(CashCollection.collected_at >= date_from)
        if date_to:
            query = query.where(CashCollection.collected_at <= date_to)
        
        # Общие суммы
        totals = await db.execute(
            query.with_only_columns(
                func.count(CashCollection.id).label('count'),
                func.sum(CashCollection.amount_collected).label('total_collected'),
                func.sum(CashCollection.expected_amount).label('total_expected'),
                func.sum(CashCollection.discrepancy).label('total_discrepancy')
            )
        )
        total_stats = totals.one()
        
        # По операторам
        by_operator = await db.execute(
            query.join(User, CashCollection.operator_id == User.id)
            .with_only_columns(
                User.id,
                User.full_name,
                func.count(CashCollection.id).label('count'),
                func.sum(CashCollection.amount_collected).label('amount')
            ).group_by(User.id, User.full_name)
            .order_by(func.sum(CashCollection.amount_collected).desc())
        )
        
        # По автоматам
        by_machine = await db.execute(
            query.join(Machine)
            .with_only_columns(
                Machine.id,
                Machine.name,
                func.count(CashCollection.id).label('count'),
                func.sum(CashCollection.amount_collected).label('amount')
            ).group_by(Machine.id, Machine.name)
            .order_by(func.sum(CashCollection.amount_collected).desc())
            .limit(10)
        )
        
        # Распределение по номиналам
        denominations = await db.execute(
            select(
                CashDenomination.denomination,
                func.sum(CashDenomination.quantity).label('total_quantity'),
                func.sum(CashDenomination.amount).label('total_amount')
            ).join(CashCollection)
            .where(
                CashCollection.status.in_(['verified', 'completed'])
            ).group_by(CashDenomination.denomination)
            .order_by(CashDenomination.denomination.desc())
        )
        
        return {
            'total_collections': total_stats.count or 0,
            'total_collected': float(total_stats.total_collected or 0),
            'total_expected': float(total_stats.total_expected or 0),
            'total_discrepancy': float(total_stats.total_discrepancy or 0),
            'discrepancy_rate': (
                float(total_stats.total_discrepancy) / float(total_stats.total_expected) * 100
            ) if total_stats.total_expected else 0,
            'by_operator': [
                {
                    'operator_id': row.id,
                    'operator_name': row.full_name,
                    'count': row.count,
                    'amount': float(row.amount)
                }
                for row in by_operator
            ],
            'by_machine': [
                {
                    'machine_id': row.id,
                    'machine_name': row.name,
                    'count': row.count,
                    'amount': float(row.amount)
                }
                for row in by_machine
            ],
            'denominations': [
                {
                    'denomination': row.denomination,
                    'quantity': row.total_quantity,
                    'amount': float(row.total_amount)
                }
                for row in denominations
            ]
        }
    
    async def get_pending_verifications(
        self,
        db: AsyncSession
    ) -> List[CashCollection]:
        """Инкассации, ожидающие проверки"""
        result = await db.execute(
            select(CashCollection)
            .where(CashCollection.status == 'completed')
            .options(
                selectinload(CashCollection.machine),
                selectinload(CashCollection.operator),
                selectinload(CashCollection.denominations)
            )
            .order_by(CashCollection.completed_at)
        )
        return result.scalars().all()