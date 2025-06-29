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
    """РЎС‚Р°С‚СѓСЃС‹ РёРЅРІРµСЃС‚РёС†РёР№"""
    ACTIVE = "active"
    PENDING = "pending"
    COMPLETED = "completed"
    TRANSFERRED = "transferred"
    CANCELLED = "cancelled"


class PayoutStatus(str, enum.Enum):
    """РЎС‚Р°С‚СѓСЃС‹ РІС‹РїР»Р°С‚"""
    SCHEDULED = "scheduled"
    PROCESSING = "processing"
    PAID = "paid"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OfferType(str, enum.Enum):
    """РўРёРїС‹ РїСЂРµРґР»РѕР¶РµРЅРёР№"""
    BUY = "buy"           # РџСЂРµРґР»РѕР¶РµРЅРёРµ РєСѓРїРёС‚СЊ РґРѕР»СЋ
    SELL = "sell"         # РџСЂРµРґР»РѕР¶РµРЅРёРµ РїСЂРѕРґР°С‚СЊ РґРѕР»СЋ
    TRANSFER = "transfer" # РџРµСЂРµРґР°С‡Р° РґРѕР»Рё


class OfferStatus(str, enum.Enum):
    """РЎС‚Р°С‚СѓСЃС‹ РїСЂРµРґР»РѕР¶РµРЅРёР№"""
    OPEN = "open"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class MachineInvestor(Base):
    """РњРѕРґРµР»СЊ РёРЅРІРµСЃС‚РѕСЂР° РІ Р°РІС‚РѕРјР°С‚"""
    __tablename__ = "machine_investors"

    machine_id: Mapped[int] = mapped_column(
        ForeignKey("machines.id", ondelete="CASCADE"),
        nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False
    )
    
    # РРЅРІРµСЃС‚РёС†РёСЏ
    investment_amount: Mapped[float] = mapped_column(
        Numeric(15, 2),
        nullable=False
    )
    share_percentage: Mapped[float] = mapped_column(
        Numeric(5, 2),
        nullable=False
    )
    investment_date: Mapped[date] = mapped_column(Date, nullable=False)
    
    # РЎС‚Р°С‚СѓСЃ
    status: Mapped[InvestmentStatus] = mapped_column(
        SQLEnum(InvestmentStatus),
        default=InvestmentStatus.ACTIVE
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Р”РѕРіРѕРІРѕСЂ
    contract_number: Mapped[Optional[str]] = mapped_column(String(100))
    contract_date: Mapped[Optional[date]] = mapped_column(Date)
    
    # Р”РѕРїРѕР»РЅРёС‚РµР»СЊРЅР°СЏ РёРЅС„РѕСЂРјР°С†РёСЏ
    notes: Mapped[Optional[str]] = mapped_column(Text)
    metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # РћС‚РЅРѕС€РµРЅРёСЏ
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
        """РћР±С‰Р°СЏ СЃСѓРјРјР° РІС‹РїР»Р°С‚"""
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
    """РњРѕРґРµР»СЊ РІС‹РїР»Р°С‚С‹ РёРЅРІРµСЃС‚РѕСЂСѓ"""
    __tablename__ = "investor_payouts"

    investment_id: Mapped[int] = mapped_column(
        ForeignKey("machine_investors.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # РџРµСЂРёРѕРґ РІС‹РїР»Р°С‚С‹
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    
    # Р Р°СЃС‡РµС‚
    total_revenue: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    total_expenses: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    net_profit: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    payout_rate: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    
    # РЎС‚Р°С‚СѓСЃ Рё РґР°С‚С‹
    status: Mapped[PayoutStatus] = mapped_column(
        SQLEnum(PayoutStatus),
        default=PayoutStatus.SCHEDULED
    )
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    paid_date: Mapped[Optional[date]] = mapped_column(Date)
    
    # РџР»Р°С‚РµР¶РЅС‹Рµ РґР°РЅРЅС‹Рµ
    payment_method: Mapped[Optional[str]] = mapped_column(String(50))
    payment_reference: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Р”РѕРїРѕР»РЅРёС‚РµР»СЊРЅР°СЏ РёРЅС„РѕСЂРјР°С†РёСЏ
    calculation_details: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    
    # РћС‚РЅРѕС€РµРЅРёСЏ
    investment: Mapped["MachineInvestor"] = relationship(
        "MachineInvestor",
        back_populates="payouts"
    )

    def __repr__(self):
        return f"<Payout {self.amount} for period {self.period_start}-{self.period_end}>"


class InvestmentOffer(Base, UUIDMixin):
    """РњРѕРґРµР»СЊ РїСЂРµРґР»РѕР¶РµРЅРёСЏ РїРѕ РёРЅРІРµСЃС‚РёС†РёРё"""
    __tablename__ = "investment_offers"

    # РЈС‡Р°СЃС‚РЅРёРєРё СЃРґРµР»РєРё
    from_investor_id: Mapped[int] = mapped_column(
        ForeignKey("machine_investors.id", ondelete="CASCADE"),
        nullable=False
    )
    to_investor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("machine_investors.id", ondelete="CASCADE")
    )
    
    # Р”РµС‚Р°Р»Рё РїСЂРµРґР»РѕР¶РµРЅРёСЏ
    offer_type: Mapped[OfferType] = mapped_column(
        SQLEnum(OfferType),
        nullable=False
    )
    share_percentage: Mapped[float] = mapped_column(
        Numeric(5, 2),
        nullable=False
    )
    price: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    
    # РЎС‚Р°С‚СѓСЃ Рё СЃСЂРѕРєРё
    status: Mapped[OfferStatus] = mapped_column(
        SQLEnum(OfferStatus),
        default=OfferStatus.OPEN
    )
    valid_until: Mapped[date] = mapped_column(Date, nullable=False)
    
    # Р”Р°С‚С‹ РґРµР№СЃС‚РІРёР№
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    responded_at: Mapped[Optional[datetime]] = mapped_column()
    
    # Р”РѕРїРѕР»РЅРёС‚РµР»СЊРЅР°СЏ РёРЅС„РѕСЂРјР°С†РёСЏ
    description: Mapped[Optional[str]] = mapped_column(Text)
    response_notes: Mapped[Optional[str]] = mapped_column(Text)
    
    # РћС‚РЅРѕС€РµРЅРёСЏ
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
    """РњРѕРґРµР»СЊ РѕС‚С‡РµС‚Р° РґР»СЏ РёРЅРІРµСЃС‚РѕСЂРѕРІ"""
    __tablename__ = "investment_reports"

    machine_id: Mapped[int] = mapped_column(
        ForeignKey("machines.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # РџРµСЂРёРѕРґ РѕС‚С‡РµС‚Р°
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    
    # Р¤РёРЅР°РЅСЃРѕРІС‹Рµ РїРѕРєР°Р·Р°С‚РµР»Рё
    revenue: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    expenses: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    net_profit: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    
    # РћРїРµСЂР°С†РёРѕРЅРЅС‹Рµ РїРѕРєР°Р·Р°С‚РµР»Рё
    total_sales: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_check: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    uptime_percent: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    
    # Р”РµС‚Р°Р»РёР·Р°С†РёСЏ
    revenue_breakdown: Mapped[dict] = mapped_column(JSON, default=dict)
    expense_breakdown: Mapped[dict] = mapped_column(JSON, default=dict)
    daily_stats: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # РЎС‚Р°С‚СѓСЃ
    is_final: Mapped[bool] = mapped_column(Boolean, default=False)
    generated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    
    # РћС‚РЅРѕС€РµРЅРёСЏ
    machine: Mapped["Machine"] = relationship("Machine")

    __table_args__ = (
        UniqueConstraint(
            "machine_id", "period_start", "period_end",
            name="uq_investment_report_period"
        ),
    )
