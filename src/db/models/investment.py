from typing import List, Optional
from datetime import date, datetime
from sqlalchemy import (
    Column, String, ForeignKey, Date, Numeric,
    Boolean, Text, JSON, Enum as SQLEnum, UniqueConstraint
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from src.db.base import Base, UUIDMixin
import enum


class InvestmentStatus(str, enum.Enum):
    """Статусы инвестиций"""
    ACTIVE = "active"
    PENDING = "pending"
    COMPLETED = "completed"
    TRANSFERRED = "transferred"
    CANCELLED = "cancelled"


class PayoutStatus(str, enum.Enum):
    """Статусы выплат"""
    SCHEDULED = "scheduled"
    PROCESSING = "processing"
    PAID = "paid"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OfferType(str, enum.Enum):
    """Типы предложений"""
    BUY = "buy"           # Предложение купить долю
    SELL = "sell"         # Предложение продать долю
    TRANSFER = "transfer" # Передача доли


class OfferStatus(str, enum.Enum):
    """Статусы предложений"""
    OPEN = "open"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class MachineInvestor(Base):
    """Модель инвестора в автомат"""
    __tablename__ = "machine_investors"

    machine_id: Mapped[int] = mapped_column(
        ForeignKey("machines.id", ondelete="CASCADE"),
        nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False
    )
    
    # Инвестиция
    investment_amount: Mapped[float] = mapped_column(
        Numeric(15, 2),
        nullable=False
    )
    share_percentage: Mapped[float] = mapped_column(
        Numeric(5, 2),
        nullable=False
    )
    investment_date: Mapped[date] = mapped_column(Date, nullable=False)
    
    # Статус
    status: Mapped[InvestmentStatus] = mapped_column(
        SQLEnum(InvestmentStatus),
        default=InvestmentStatus.ACTIVE
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Договор
    contract_number: Mapped[Optional[str]] = mapped_column(String(100))
    contract_date: Mapped[Optional[date]] = mapped_column(Date)
    
    # Дополнительная информация
    notes: Mapped[Optional[str]] = mapped_column(Text)
    metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Отношения
    machine: Mapped["Machine"] = relationship(
        "Machine",
        back_populates="investors"
    )
    investor: Mapped["User"] = relationship(
        "User",
        back_populates="investments"
    )
    
    payouts: Mapped[List["InvestorPayout"]] = relationship(
        "InvestorPayout",
        back_populates="investment",
        cascade="all, delete-orphan"
    )
    
    offers_from: Mapped[List["InvestmentOffer"]] = relationship(
        "InvestmentOffer",
        foreign_keys="InvestmentOffer.from_investor_id",
        back_populates="from_investor"
    )
    
    offers_to: Mapped[List["InvestmentOffer"]] = relationship(
        "InvestmentOffer",
        foreign_keys="InvestmentOffer.to_investor_id",
        back_populates="to_investor"
    )

    __table_args__ = (
        UniqueConstraint("machine_id", "user_id", name="uq_machine_investor"),
    )

    def __repr__(self):
        return f"<MachineInvestor {self.investor.display_name} - {self.share_percentage}%>"

    @property
    def total_payouts(self) -> float:
        """Общая сумма выплат"""
        return sum(
            float(payout.amount)
            for payout in self.payouts
            if payout.status == PayoutStatus.PAID
        )

    @property
    def roi(self) -> float:
        """Return on Investment"""
        if self.investment_amount == 0:
            return 0
        return (self.total_payouts / float(self.investment_amount)) * 100


class InvestorPayout(Base, UUIDMixin):
    """Модель выплаты инвестору"""
    __tablename__ = "investor_payouts"

    investment_id: Mapped[int] = mapped_column(
        ForeignKey("machine_investors.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Период выплаты
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    
    # Расчет
    total_revenue: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    total_expenses: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    net_profit: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    payout_rate: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    
    # Статус и даты
    status: Mapped[PayoutStatus] = mapped_column(
        SQLEnum(PayoutStatus),
        default=PayoutStatus.SCHEDULED
    )
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    paid_date: Mapped[Optional[date]] = mapped_column(Date)
    
    # Платежные данные
    payment_method: Mapped[Optional[str]] = mapped_column(String(50))
    payment_reference: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Дополнительная информация
    calculation_details: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    
    # Отношения
    investment: Mapped["MachineInvestor"] = relationship(
        "MachineInvestor",
        back_populates="payouts"
    )

    def __repr__(self):
        return f"<Payout {self.amount} for period {self.period_start}-{self.period_end}>"


class InvestmentOffer(Base, UUIDMixin):
    """Модель предложения по инвестиции"""
    __tablename__ = "investment_offers"

    # Участники сделки
    from_investor_id: Mapped[int] = mapped_column(
        ForeignKey("machine_investors.id", ondelete="CASCADE"),
        nullable=False
    )
    to_investor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("machine_investors.id", ondelete="CASCADE")
    )
    
    # Детали предложения
    offer_type: Mapped[OfferType] = mapped_column(
        SQLEnum(OfferType),
        nullable=False
    )
    share_percentage: Mapped[float] = mapped_column(
        Numeric(5, 2),
        nullable=False
    )
    price: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    
    # Статус и сроки
    status: Mapped[OfferStatus] = mapped_column(
        SQLEnum(OfferStatus),
        default=OfferStatus.OPEN
    )
    valid_until: Mapped[date] = mapped_column(Date, nullable=False)
    
    # Даты действий
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    responded_at: Mapped[Optional[datetime]] = mapped_column()
    
    # Дополнительная информация
    description: Mapped[Optional[str]] = mapped_column(Text)
    response_notes: Mapped[Optional[str]] = mapped_column(Text)
    
    # Отношения
    from_investor: Mapped["MachineInvestor"] = relationship(
        "MachineInvestor",
        foreign_keys=[from_investor_id],
        back_populates="offers_from"
    )
    
    to_investor: Mapped[Optional["MachineInvestor"]] = relationship(
        "MachineInvestor",
        foreign_keys=[to_investor_id],
        back_populates="offers_to"
    )

    def __repr__(self):
        return f"<InvestmentOffer {self.offer_type} {self.share_percentage}% for {self.price}>"


class InvestmentReport(Base):
    """Модель отчета для инвесторов"""
    __tablename__ = "investment_reports"

    machine_id: Mapped[int] = mapped_column(
        ForeignKey("machines.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Период отчета
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    
    # Финансовые показатели
    revenue: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    expenses: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    net_profit: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    
    # Операционные показатели
    total_sales: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_check: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    uptime_percent: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    
    # Детализация
    revenue_breakdown: Mapped[dict] = mapped_column(JSON, default=dict)
    expense_breakdown: Mapped[dict] = mapped_column(JSON, default=dict)
    daily_stats: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Статус
    is_final: Mapped[bool] = mapped_column(Boolean, default=False)
    generated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    
    # Отношения
    machine: Mapped["Machine"] = relationship("Machine")

    __table_args__ = (
        UniqueConstraint(
            "machine_id", "period_start", "period_end",
            name="uq_investment_report_period"
        ),
    )