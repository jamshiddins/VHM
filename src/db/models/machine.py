from typing import List, Optional
from datetime import date
from sqlalchemy import (
    Column, String, ForeignKey, Date, JSON, 
    Numeric, Enum as SQLEnum
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from src.db.base import Base, SoftDeleteMixin, UUIDMixin
import enum


class MachineType(str, enum.Enum):
    """Типы автоматов"""
    COFFEE = "coffee"
    SNACK = "snack"
    COMBO = "combo"
    WATER = "water"


class MachineStatus(str, enum.Enum):
    """Статусы автоматов"""
    ACTIVE = "active"
    MAINTENANCE = "maintenance"
    INACTIVE = "inactive"
    BROKEN = "broken"


class Machine(Base, UUIDMixin, SoftDeleteMixin):
    """Модель автомата"""
    __tablename__ = "machines"

    # Основные поля
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[MachineType] = mapped_column(SQLEnum(MachineType), nullable=False)
    model: Mapped[Optional[str]] = mapped_column(String(100))
    serial_number: Mapped[Optional[str]] = mapped_column(String(100))
    status: Mapped[MachineStatus] = mapped_column(
        SQLEnum(MachineStatus), 
        default=MachineStatus.ACTIVE,
        index=True
    )
    
    # Локация
    location_address: Mapped[Optional[str]] = mapped_column(String)
    location_lat: Mapped[Optional[float]] = mapped_column(Numeric(10, 8))
    location_lng: Mapped[Optional[float]] = mapped_column(Numeric(11, 8))
    
    # Даты
    installation_date: Mapped[Optional[date]] = mapped_column(Date)
    last_service_date: Mapped[Optional[date]] = mapped_column(Date)
    
    # Ответственный
    responsible_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    
    # Настройки и метаданные
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Отношения
    responsible_user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="managed_machines",
        foreign_keys=[responsible_user_id]
    )
    
    routes: Mapped[List["MachineRoute"]] = relationship(
        "MachineRoute",
        back_populates="machine",
        cascade="all, delete-orphan"
    )
    
    tasks: Mapped[List["MachineTask"]] = relationship(
        "MachineTask",
        back_populates="machine",
        cascade="all, delete-orphan"
    )
    
    inventory: Mapped[List["Inventory"]] = relationship(
        "Inventory",
        primaryjoin="and_(Machine.id==Inventory.location_id, Inventory.location_type=='machine')",
        viewonly=True
    )
    
    sales: Mapped[List["Sale"]] = relationship(
        "Sale",
        back_populates="machine"
    )
    
    investors: Mapped[List["MachineInvestor"]] = relationship(
        "MachineInvestor",
        back_populates="machine",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Machine {self.code}: {self.name}>"

    @property
    def full_address(self) -> str:
        """Полный адрес"""
        return self.location_address or "Адрес не указан"

    @property
    def coordinates(self) -> Optional[tuple]:
        """Координаты"""
        if self.location_lat and self.location_lng:
            return (float(self.location_lat), float(self.location_lng))
        return None

    @property
    def is_operational(self) -> bool:
        """Работает ли автомат"""
        return self.status == MachineStatus.ACTIVE

    @property
    def total_investment(self) -> float:
        """Общая сумма инвестиций"""
        return sum(inv.investment_amount for inv in self.investors if inv.is_active)

    @property
    def investor_shares(self) -> dict:
        """Доли инвесторов"""
        return {
            inv.investor.display_name: float(inv.share_percentage)
            for inv in self.investors
            if inv.is_active
        }