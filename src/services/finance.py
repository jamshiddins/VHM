from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models.finance import (
    FinanceAccount, FinanceTransaction, Sale, Payment,
    TransactionType, TransactionCategory, PaymentMethod,
    AccountType, ExpenseBudget
)
from src.db.models.machine import Machine
from src.core.exceptions import (
    InsufficientFunds, TransactionNotFound, InvalidTransactionType
)


class FinanceService:
    """Сервис для работы с финансами"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    # === Работа со счетами ===
    
    async def get_account_by_id(self, account_id: int) -> Optional[FinanceAccount]:
        """Получение счета по ID"""
        return await self.session.get(FinanceAccount, account_id)
    
    async def get_account_by_code(self, code: str) -> Optional[FinanceAccount]:
        """Получение счета по коду"""
        query = select(FinanceAccount).where(FinanceAccount.code == code)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_accounts_list(
        self,
        account_type: Optional[AccountType] = None,
        is_active: Optional[bool] = True
    ) -> List[FinanceAccount]:
        """Получение списка счетов"""
        query = select(FinanceAccount)
        
        conditions = []
        if account_type:
            conditions.append(FinanceAccount.type == account_type)
        if is_active is not None:
            conditions.append(FinanceAccount.is_active == is_active)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        result = await self.session.execute(query.order_by(FinanceAccount.name))
        return list(result.scalars().all())
    
    async def create_account(
        self,
        code: str,
        name: str,
        account_type: AccountType,
        currency: str = "UZS",
        initial_balance: Decimal = Decimal('0'),
        description: Optional[str] = None
    ) -> FinanceAccount:
        """Создание нового счета"""
        account = FinanceAccount(
            code=code,
            name=name,
            type=account_type,
            currency=currency,
            balance=initial_balance,
            description=description
        )
        
        self.session.add(account)
        await self.session.commit()
        await self.session.refresh(account)
        
        return account
    
    async def update_account_balance(
        self,
        account_id: int,
        amount: Decimal,
        operation: str = 'add'  # 'add', 'subtract', 'set'
    ) -> FinanceAccount:
        """Обновление баланса счета"""
        account = await self.get_account_by_id(account_id)
        if not account:
            raise TransactionNotFound(f"Счет с ID {account_id} не найден")
        
        if operation == 'add':
            account.balance += amount
        elif operation == 'subtract':
            if account.balance < amount:
                raise InsufficientFunds(
                    f"Недостаточно средств на счете {account.name}. "
                    f"Баланс: {account.balance}, требуется: {amount}"
                )
            account.balance -= amount
        elif operation == 'set':
            account.balance = amount
        
        await self.session.commit()
        await self.session.refresh(account)
        
        return account
    
    # === Работа с транзакциями ===
    
    async def create_transaction(
        self,
        transaction_type: TransactionType,
        amount: Decimal,
        created_by_id: int,
        category: Optional[TransactionCategory] = None,
        from_account_id: Optional[int] = None,
        to_account_id: Optional[int] = None,
        description: Optional[str] = None,
        reference_type: Optional[str] = None,
        reference_id: Optional[int] = None,
        attachments: Optional[List[str]] = None,
        action_timestamp: Optional[datetime] = None
    ) -> FinanceTransaction:
        """Создание финансовой транзакции"""
        # Валидация
        if transaction_type == TransactionType.TRANSFER:
            if not from_account_id or not to_account_id:
                raise InvalidTransactionType(
                    "Для перевода требуется указать оба счета"
                )
        elif transaction_type == TransactionType.INCOME:
            if not to_account_id:
                raise InvalidTransactionType(
                    "Для дохода требуется указать счет получателя"
                )
        elif transaction_type == TransactionType.EXPENSE:
            if not from_account_id:
                raise InvalidTransactionType(
                    "Для расхода требуется указать счет списания"
                )
        
        # Создаем транзакцию
        transaction = FinanceTransaction(
            type=transaction_type,
            category=category,
            from_account_id=from_account_id,
            to_account_id=to_account_id,
            amount=amount,
            description=description,
            reference_type=reference_type,
            reference_id=reference_id,
            created_by_id=created_by_id,
            attachments=attachments or [],
            action_timestamp=action_timestamp or datetime.utcnow()
        )
        
        self.session.add(transaction)
        
        # Обновляем балансы счетов
        if from_account_id:
            await self.update_account_balance(
                from_account_id, amount, 'subtract'
            )
        
        if to_account_id:
            await self.update_account_balance(
                to_account_id, amount, 'add'
            )
        
        await self.session.commit()
        await self.session.refresh(transaction)
        
        return transaction
    
    async def get_transactions(
        self,
        transaction_type: Optional[TransactionType] = None,
        category: Optional[TransactionCategory] = None,
        account_id: Optional[int] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        limit: int = 100,
        offset: int = 0
    ) -> tuple[List[FinanceTransaction], int]:
        """Получение списка транзакций"""
        query = select(FinanceTransaction).options(
            selectinload(FinanceTransaction.from_account),
            selectinload(FinanceTransaction.to_account),
            selectinload(FinanceTransaction.created_by)
        )
        
        conditions = []
        
        if transaction_type:
            conditions.append(FinanceTransaction.type == transaction_type)
        
        if category:
            conditions.append(FinanceTransaction.category == category)
        
        if account_id:
            conditions.append(
                or_(
                    FinanceTransaction.from_account_id == account_id,
                    FinanceTransaction.to_account_id == account_id
                )
            )
        
        if date_from:
            conditions.append(FinanceTransaction.action_timestamp >= date_from)
        
        if date_to:
            conditions.append(
                FinanceTransaction.action_timestamp <= date_to + timedelta(days=1)
            )
        
        if conditions:
            query = query.where(and_(*conditions))
        
        # Подсчет общего количества
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0
        
        # Применяем пагинацию и сортировку
        query = query.order_by(desc(FinanceTransaction.action_timestamp))
        query = query.offset(offset).limit(limit)
        
        result = await self.session.execute(query)
        transactions = list(result.scalars().all())
        
        return transactions, total
    
    # === Работа с продажами ===
    
    async def record_sale(
        self,
        machine_id: int,
        product_id: int,
        quantity: int,
        unit_price: Decimal,
        payment_method: PaymentMethod,
        transaction_id: Optional[str] = None,
        action_timestamp: Optional[datetime] = None
    ) -> Sale:
        """Запись продажи"""
        total_amount = quantity * unit_price
        
        sale = Sale(
            machine_id=machine_id,
            product_id=product_id,
            quantity=quantity,
            unit_price=unit_price,
            total_amount=total_amount,
            payment_method=payment_method,
            transaction_id=transaction_id,
            action_timestamp=action_timestamp or datetime.utcnow()
        )
        
        self.session.add(sale)
        
        # Создаем финансовую транзакцию
        account_code_map = {
            PaymentMethod.CASH: "cash_main",
            PaymentMethod.PAYME: "payme",
            PaymentMethod.CLICK: "click",
            PaymentMethod.UZUM: "uzum",
            PaymentMethod.BANK_TRANSFER: "bank_main"
        }
        
        account_code = account_code_map.get(payment_method, "cash_main")
        account = await self.get_account_by_code(account_code)
        
        if account:
            await self.create_transaction(
                transaction_type=TransactionType.INCOME,
                amount=total_amount,
                to_account_id=account.id,
                category=TransactionCategory.SALES,
                description=f"Продажа #{sale.id}",
                reference_type="sale",
                reference_id=sale.id,
                created_by_id=1,  # Системный пользователь
                action_timestamp=sale.action_timestamp
            )
        
        await self.session.commit()
        await self.session.refresh(sale)
        
        return sale
    
    async def get_sales_report(
        self,
        machine_id: Optional[int] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None
    ) -> Dict[str, Any]:
        """Получение отчета по продажам"""
        query = select(Sale).options(
            selectinload(Sale.machine),
            selectinload(Sale.product)
        )
        
        conditions = []
        
        if machine_id:
            conditions.append(Sale.machine_id == machine_id)
        
        if date_from:
            conditions.append(Sale.action_timestamp >= date_from)
        
        if date_to:
            conditions.append(Sale.action_timestamp <= date_to + timedelta(days=1))
        
        if conditions:
            query = query.where(and_(*conditions))
        
        result = await self.session.execute(query)
        sales = list(result.scalars().all())
        
        # Подсчет статистики
        total_sales = len(sales)
        total_revenue = sum(float(sale.total_amount) for sale in sales)
        
        # Группировка по методам оплаты
        by_payment_method = {}
        for sale in sales:
            method = sale.payment_method.value if sale.payment_method else 'unknown'
            if method not in by_payment_method:
                by_payment_method[method] = {'count': 0, 'amount': 0}
            
            by_payment_method[method]['count'] += 1
            by_payment_method[method]['amount'] += float(sale.total_amount)
        
        # Группировка по продуктам
        by_product = {}
        for sale in sales:
            product_name = sale.product.name
            if product_name not in by_product:
                by_product[product_name] = {'count': 0, 'amount': 0}
            
            by_product[product_name]['count'] += sale.quantity
            by_product[product_name]['amount'] += float(sale.total_amount)
        
        # Средний чек
        avg_check = total_revenue / total_sales if total_sales > 0 else 0
        
        return {
            'period': {
                'from': date_from,
                'to': date_to
            },
            'total_sales': total_sales,
            'total_revenue': total_revenue,
            'avg_check': avg_check,
            'by_payment_method': by_payment_method,
            'by_product': sorted(
                by_product.items(),
                key=lambda x: x[1]['amount'],
                reverse=True
            )[:10]  # Топ-10 продуктов
        }
    
    # === Сверка платежей ===
    
    async def reconcile_payments(
        self,
        date_from: date,
        date_to: date
    ) -> Dict[str, Any]:
        """Сверка платежей из разных источников"""
        # Получаем продажи из автоматов
        sales_query = select(Sale).where(
            and_(
                Sale.action_timestamp >= date_from,
                Sale.action_timestamp <= date_to + timedelta(days=1)
            )
        )
        sales_result = await self.session.execute(sales_query)
        sales = list(sales_result.scalars().all())
        
        # Получаем платежи из разных источников
        payments_query = select(Payment).where(
            and_(
                Payment.payment_date >= date_from,
                Payment.payment_date <= date_to + timedelta(days=1)
            )
        )
        payments_result = await self.session.execute(payments_query)
        payments = list(payments_result.scalars().all())
        
        # Группируем по источникам
        sales_by_method = {}
        for sale in sales:
            method = sale.payment_method.value if sale.payment_method else 'unknown'
            if method not in sales_by_method:
                sales_by_method[method] = []
            sales_by_method[method].append(sale)
        
        payments_by_source = {}
        for payment in payments:
            source = payment.source
            if source not in payments_by_source:
                payments_by_source[source] = []
            payments_by_source[source].append(payment)
        
        # Сверка
        reconciliation = {
            'period': {
                'from': date_from,
                'to': date_to
            },
            'sources': {},
            'discrepancies': []
        }
        
        # TODO: Реализовать детальную логику сверки
        
        return reconciliation
    
    # === Бюджеты и планирование ===
    
    async def get_expense_budget(
        self,
        year: int,
        month: int,
        category: Optional[TransactionCategory] = None
    ) -> List[ExpenseBudget]:
        """Получение бюджетов расходов"""
        query = select(ExpenseBudget).where(
            and_(
                ExpenseBudget.year == year,
                ExpenseBudget.month == month
            )
        )
        
        if category:
            query = query.where(ExpenseBudget.category == category)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def update_budget_actuals(
        self,
        year: int,
        month: int
    ):
        """Обновление фактических расходов в бюджете"""
        # Получаем все расходы за месяц
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)
        
        expenses_query = select(
            FinanceTransaction.category,
            func.sum(FinanceTransaction.amount)
        ).where(
            and_(
                FinanceTransaction.type == TransactionType.EXPENSE,
                FinanceTransaction.action_timestamp >= start_date,
                FinanceTransaction.action_timestamp <= end_date + timedelta(days=1),
                FinanceTransaction.category.isnot(None)
            )
        ).group_by(FinanceTransaction.category)
        
        result = await self.session.execute(expenses_query)
        actual_expenses = dict(result.all())
        
        # Обновляем бюджеты
        budgets = await self.get_expense_budget(year, month)
        
        for budget in budgets:
            budget.actual_amount = actual_expenses.get(budget.category, Decimal('0'))
        
        await self.session.commit()
    
    # === Финансовая аналитика ===
    
    async def get_financial_summary(
        self,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None
    ) -> Dict[str, Any]:
        """Получение финансовой сводки"""
        if not date_from:
            date_from = date.today().replace(day=1)
        if not date_to:
            date_to = date.today()
        
        # Получаем все транзакции за период
        transactions, _ = await self.get_transactions(
            date_from=date_from,
            date_to=date_to,
            limit=10000  # Большой лимит для аналитики
        )
        
        # Подсчет по типам
        income = sum(
            float(t.amount) for t in transactions 
            if t.type == TransactionType.INCOME
        )
        expenses = sum(
            float(t.amount) for t in transactions 
            if t.type == TransactionType.EXPENSE
        )
        
        # Группировка расходов по категориям
        expenses_by_category = {}
        for t in transactions:
            if t.type == TransactionType.EXPENSE and t.category:
                cat = t.category.value
                if cat not in expenses_by_category:
                    expenses_by_category[cat] = 0
                expenses_by_category[cat] += float(t.amount)
        
        # Баланс счетов
        accounts = await self.get_accounts_list()
        total_balance = sum(float(acc.balance) for acc in accounts)
        
        accounts_balance = [
            {
                'code': acc.code,
                'name': acc.name,
                'type': acc.type.value,
                'balance': float(acc.balance),
                'currency': acc.currency
            }
            for acc in accounts
        ]
        
        return {
            'period': {
                'from': date_from,
                'to': date_to
            },
            'income': income,
            'expenses': expenses,
            'profit': income - expenses,
            'expenses_by_category': expenses_by_category,
            'total_balance': total_balance,
            'accounts_balance': accounts_balance,
            'profit_margin': (income - expenses) / income * 100 if income > 0 else 0
        }
    
    async def get_cash_flow(
        self,
        date_from: date,
        date_to: date,
        group_by: str = 'day'  # day, week, month
    ) -> List[Dict[str, Any]]:
        """Получение движения денежных средств"""
        transactions, _ = await self.get_transactions(
            date_from=date_from,
            date_to=date_to,
            limit=10000
        )
        
        # Группировка по периодам
        cash_flow = {}
        
        for t in transactions:
            if group_by == 'day':
                period = t.action_timestamp.date()
            elif group_by == 'week':
                period = t.action_timestamp.date() - timedelta(
                    days=t.action_timestamp.weekday()
                )
            elif group_by == 'month':
                period = t.action_timestamp.date().replace(day=1)
            else:
                period = t.action_timestamp.date()
            
            if period not in cash_flow:
                cash_flow[period] = {
                    'period': period,
                    'income': 0,
                    'expenses': 0,
                    'net': 0
                }
            
            if t.type == TransactionType.INCOME:
                cash_flow[period]['income'] += float(t.amount)
            elif t.type == TransactionType.EXPENSE:
                cash_flow[period]['expenses'] += float(t.amount)
        
        # Вычисляем чистый поток
        for period_data in cash_flow.values():
            period_data['net'] = period_data['income'] - period_data['expenses']
        
        # Сортируем по дате
        return sorted(cash_flow.values(), key=lambda x: x['period'])