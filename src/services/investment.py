from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models.investment import (
    MachineInvestor, InvestorPayout, InvestmentOffer, InvestmentReport,
    InvestmentStatus, PayoutStatus, OfferType, OfferStatus
)
from src.db.models.machine import Machine
from src.db.models.user import User
from src.db.models.finance import Sale, FinanceTransaction, TransactionCategory
from src.core.exceptions import (
    InvestmentNotFound, InvestmentAlreadyExists, InvalidSharePercentage
)
from src.core.config import settings


class InvestmentService:
    """Сервис для работы с инвестициями"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    # === Управление инвестициями ===
    
    async def create_investment(
        self,
        machine_id: int,
        user_id: int,
        investment_amount: Decimal,
        share_percentage: Decimal,
        contract_number: Optional[str] = None,
        contract_date: Optional[date] = None,
        notes: Optional[str] = None
    ) -> MachineInvestor:
        """Создание новой инвестиции"""
        # Проверяем существование
        existing = await self.session.execute(
            select(MachineInvestor).where(
                and_(
                    MachineInvestor.machine_id == machine_id,
                    MachineInvestor.user_id == user_id,
                    MachineInvestor.is_active == True
                )
            )
        )
        if existing.scalar_one_or_none():
            raise InvestmentAlreadyExists(
                "У пользователя уже есть активная инвестиция в этот автомат"
            )
        
        # Проверяем общую долю
        total_shares_query = select(
            func.sum(MachineInvestor.share_percentage)
        ).where(
            and_(
                MachineInvestor.machine_id == machine_id,
                MachineInvestor.is_active == True
            )
        )
        total_shares_result = await self.session.execute(total_shares_query)
        total_shares = total_shares_result.scalar() or Decimal('0')
        
        if total_shares + share_percentage > Decimal('100'):
            raise InvalidSharePercentage(
                f"Превышена максимальная доля. Доступно: {100 - total_shares}%"
            )
        
        # Создаем инвестицию
        investment = MachineInvestor(
            machine_id=machine_id,
            user_id=user_id,
            investment_amount=investment_amount,
            share_percentage=share_percentage,
            investment_date=date.today(),
            contract_number=contract_number,
            contract_date=contract_date,
            notes=notes,
            status=InvestmentStatus.ACTIVE
        )
        
        self.session.add(investment)
        await self.session.commit()
        await self.session.refresh(investment)
        
        return investment
    
    async def get_investment_by_id(self, investment_id: int) -> Optional[MachineInvestor]:
        """Получение инвестиции по ID"""
        query = select(MachineInvestor).options(
            selectinload(MachineInvestor.machine),
            selectinload(MachineInvestor.investor),
            selectinload(MachineInvestor.payouts)
        ).where(MachineInvestor.id == investment_id)
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_user_investments(
        self,
        user_id: int,
        is_active: Optional[bool] = None
    ) -> List[MachineInvestor]:
        """Получение инвестиций пользователя"""
        query = select(MachineInvestor).options(
            selectinload(MachineInvestor.machine),
            selectinload(MachineInvestor.payouts)
        ).where(MachineInvestor.user_id == user_id)
        
        if is_active is not None:
            query = query.where(MachineInvestor.is_active == is_active)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_machine_investors(
        self,
        machine_id: int,
        is_active: bool = True
    ) -> List[MachineInvestor]:
        """Получение инвесторов автомата"""
        query = select(MachineInvestor).options(
            selectinload(MachineInvestor.investor)
        ).where(
            and_(
                MachineInvestor.machine_id == machine_id,
                MachineInvestor.is_active == is_active
            )
        )
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    # === Расчет и создание выплат ===
    
    async def calculate_payouts(
        self,
        machine_id: int,
        period_start: date,
        period_end: date
    ) -> List[Dict[str, Any]]:
        """Расчет выплат для инвесторов автомата"""
        # Получаем инвесторов
        investors = await self.get_machine_investors(machine_id)
        if not investors:
            return []
        
        # Получаем доходы за период
        revenue_query = select(func.sum(Sale.total_amount)).where(
            and_(
                Sale.machine_id == machine_id,
                Sale.action_timestamp >= period_start,
                Sale.action_timestamp <= period_end + timedelta(days=1)
            )
        )
        revenue_result = await self.session.execute(revenue_query)
        total_revenue = revenue_result.scalar() or Decimal('0')
        
        # Получаем расходы за период
        expenses_query = select(
            func.sum(FinanceTransaction.amount)
        ).where(
            and_(
                FinanceTransaction.type == 'expense',
                FinanceTransaction.reference_type == 'machine',
                FinanceTransaction.reference_id == machine_id,
                FinanceTransaction.action_timestamp >= period_start,
                FinanceTransaction.action_timestamp <= period_end + timedelta(days=1)
            )
        )
        expenses_result = await self.session.execute(expenses_query)
        total_expenses = expenses_result.scalar() or Decimal('0')
        
        # Чистая прибыль
        net_profit = total_revenue - total_expenses
        
        # Прибыль для распределения (70% инвесторам по умолчанию)
        investor_profit = net_profit * Decimal(str(settings.INVESTOR_SHARE_PERCENT / 100))
        
        # Расчет выплат
        payouts = []
        for investor in investors:
            # Доля инвестора от общей прибыли инвесторов
            investor_share = investor.share_percentage / Decimal('100')
            payout_amount = investor_profit * investor_share
            
            payouts.append({
                'investment_id': investor.id,
                'investor_id': investor.user_id,
                'investor_name': investor.investor.full_name,
                'share_percentage': float(investor.share_percentage),
                'total_revenue': float(total_revenue),
                'total_expenses': float(total_expenses),
                'net_profit': float(net_profit),
                'payout_amount': float(payout_amount),
                'calculation_details': {
                    'investor_profit_pool': float(investor_profit),
                    'investor_share': float(investor_share),
                    'formula': f"{investor_profit} * {investor_share} = {payout_amount}"
                }
            })
        
        return payouts
    
    async def create_payouts(
        self,
        machine_id: int,
        period_start: date,
        period_end: date,
        scheduled_date: Optional[date] = None
    ) -> List[InvestorPayout]:
        """Создание выплат для инвесторов"""
        # Рассчитываем выплаты
        payout_calculations = await self.calculate_payouts(
            machine_id, period_start, period_end
        )
        
        if not payout_calculations:
            return []
        
        # Дата выплаты (по умолчанию через 7 дней)
        if not scheduled_date:
            scheduled_date = date.today() + timedelta(days=7)
        
        # Создаем записи о выплатах
        payouts = []
        for calc in payout_calculations:
            if calc['payout_amount'] > 0:  # Только если есть что выплачивать
                payout = InvestorPayout(
                    investment_id=calc['investment_id'],
                    period_start=period_start,
                    period_end=period_end,
                    total_revenue=Decimal(str(calc['total_revenue'])),
                    total_expenses=Decimal(str(calc['total_expenses'])),
                    net_profit=Decimal(str(calc['net_profit'])),
                    payout_rate=Decimal(str(calc['share_percentage'])),
                    amount=Decimal(str(calc['payout_amount'])),
                    scheduled_date=scheduled_date,
                    status=PayoutStatus.SCHEDULED,
                    calculation_details=calc['calculation_details']
                )
                self.session.add(payout)
                payouts.append(payout)
        
        await self.session.commit()
        return payouts
    
    async def process_payout(
        self,
        payout_id: int,
        payment_method: str,
        payment_reference: Optional[str] = None,
        notes: Optional[str] = None
    ) -> InvestorPayout:
        """Обработка выплаты"""
        payout = await self.session.get(InvestorPayout, payout_id)
        if not payout:
            raise InvestmentNotFound(f"Выплата с ID {payout_id} не найдена")
        
        if payout.status != PayoutStatus.SCHEDULED:
            raise ValueError(f"Выплата уже обработана со статусом: {payout.status}")
        
        # Обновляем статус
        payout.status = PayoutStatus.PROCESSING
        payout.payment_method = payment_method
        payout.payment_reference = payment_reference
        
        if notes:
            payout.notes = notes
        
        # TODO: Интеграция с платежными системами
        
        # После успешной выплаты
        payout.status = PayoutStatus.PAID
        payout.paid_date = date.today()
        
        await self.session.commit()
        await self.session.refresh(payout)
        
        return payout
    
    # === Предложения о купле-продаже долей ===
    
    async def create_offer(
        self,
        from_investor_id: int,
        offer_type: OfferType,
        share_percentage: Decimal,
        price: Decimal,
        valid_days: int = 30,
        to_investor_id: Optional[int] = None,
        description: Optional[str] = None
    ) -> InvestmentOffer:
        """Создание предложения"""
        offer = InvestmentOffer(
            from_investor_id=from_investor_id,
            to_investor_id=to_investor_id,
            offer_type=offer_type,
            share_percentage=share_percentage,
            price=price,
            valid_until=date.today() + timedelta(days=valid_days),
            description=description,
            status=OfferStatus.OPEN
        )
        
        self.session.add(offer)
        await self.session.commit()
        await self.session.refresh(offer)
        
        return offer
    
    async def respond_to_offer(
        self,
        offer_id: int,
        accept: bool,
        response_notes: Optional[str] = None
    ) -> InvestmentOffer:
        """Ответ на предложение"""
        offer = await self.session.get(InvestmentOffer, offer_id)
        if not offer:
            raise InvestmentNotFound(f"Предложение с ID {offer_id} не найдено")
        
        if offer.status != OfferStatus.OPEN:
            raise ValueError(f"Предложение уже обработано со статусом: {offer.status}")
        
        if offer.valid_until < date.today():
            offer.status = OfferStatus.EXPIRED
        else:
            offer.status = OfferStatus.ACCEPTED if accept else OfferStatus.REJECTED
            offer.responded_at = datetime.utcnow()
            offer.response_notes = response_notes
            
            if accept and offer.offer_type == OfferType.BUY:
                # TODO: Обработка передачи доли
                pass
        
        await self.session.commit()
        await self.session.refresh(offer)
        
        return offer
    
    # === Отчеты для инвесторов ===
    
    async def create_investment_report(
        self,
        machine_id: int,
        period_start: date,
        period_end: date
    ) -> InvestmentReport:
        """Создание отчета для инвесторов"""
        # Получаем данные о продажах
        sales_query = select(Sale).where(
            and_(
                Sale.machine_id == machine_id,
                Sale.action_timestamp >= period_start,
                Sale.action_timestamp <= period_end + timedelta(days=1)
            )
        )
        sales_result = await self.session.execute(sales_query)
        sales = list(sales_result.scalars().all())
        
        total_sales = len(sales)
        revenue = sum(float(sale.total_amount) for sale in sales)
        avg_check = revenue / total_sales if total_sales > 0 else 0
        
        # Получаем расходы
        expenses_query = select(
            FinanceTransaction.category,
            func.sum(FinanceTransaction.amount)
        ).where(
            and_(
                FinanceTransaction.type == 'expense',
                FinanceTransaction.reference_type == 'machine',
                FinanceTransaction.reference_id == machine_id,
                FinanceTransaction.action_timestamp >= period_start,
                FinanceTransaction.action_timestamp <= period_end + timedelta(days=1)
            )
        ).group_by(FinanceTransaction.category)
        
        expenses_result = await self.session.execute(expenses_query)
        expense_breakdown = dict(expenses_result.all())
        total_expenses = sum(expense_breakdown.values())
        
        # Группировка продаж по дням
        daily_stats = {}
        for sale in sales:
            day = sale.action_timestamp.date()
            if day not in daily_stats:
                daily_stats[day] = {'count': 0, 'revenue': 0}
            daily_stats[day]['count'] += 1
            daily_stats[day]['revenue'] += float(sale.total_amount)
        
        # Расчет uptime (примерный)
        total_days = (period_end - period_start).days + 1
        operational_days = len(daily_stats)
        uptime_percent = (operational_days / total_days * 100) if total_days > 0 else 0
        
        # Создаем отчет
        report = InvestmentReport(
            machine_id=machine_id,
            report_date=date.today(),
            period_start=period_start,
            period_end=period_end,
            revenue=Decimal(str(revenue)),
            expenses=Decimal(str(total_expenses)),
            net_profit=Decimal(str(revenue - total_expenses)),
            total_sales=total_sales,
            avg_check=Decimal(str(avg_check)),
            uptime_percent=Decimal(str(uptime_percent)),
            revenue_breakdown={'sales': revenue},
            expense_breakdown={
                k.value if k else 'other': float(v) 
                for k, v in expense_breakdown.items()
            },
            daily_stats={
                str(k): v for k, v in daily_stats.items()
            }
        )
        
        self.session.add(report)
        await self.session.commit()
        await self.session.refresh(report)
        
        return report
    
    async def get_investor_portfolio(
        self,
        user_id: int
    ) -> Dict[str, Any]:
        """Получение портфеля инвестора"""
        investments = await self.get_user_investments(user_id, is_active=True)
        
        total_invested = sum(float(inv.investment_amount) for inv in investments)
        total_machines = len(investments)
        
        # Подсчет выплат
        total_payouts = 0
        pending_payouts = 0
        
        for inv in investments:
            for payout in inv.payouts:
                if payout.status == PayoutStatus.PAID:
                    total_payouts += float(payout.amount)
                elif payout.status == PayoutStatus.SCHEDULED:
                    pending_payouts += float(payout.amount)
        
        # ROI
        roi = (total_payouts / total_invested * 100) if total_invested > 0 else 0
        
        # Детали по автоматам
        machines_details = []
        for inv in investments:
            last_payout = None
            if inv.payouts:
                last_payout = max(inv.payouts, key=lambda p: p.created_at)
            
            machines_details.append({
                'machine': {
                    'id': inv.machine.id,
                    'code': inv.machine.code,
                    'name': inv.machine.name,
                    'status': inv.machine.status.value
                },
                'investment': {
                    'amount': float(inv.investment_amount),
                    'share': float(inv.share_percentage),
                    'date': inv.investment_date,
                    'total_payouts': sum(
                        float(p.amount) for p in inv.payouts 
                        if p.status == PayoutStatus.PAID
                    )
                },
                'last_payout': {
                    'date': last_payout.paid_date,
                    'amount': float(last_payout.amount)
                } if last_payout and last_payout.status == PayoutStatus.PAID else None
            })
        
        return {
            'summary': {
                'total_invested': total_invested,
                'total_machines': total_machines,
                'total_payouts': total_payouts,
                'pending_payouts': pending_payouts,
                'roi': roi
            },
            'machines': machines_details
        }