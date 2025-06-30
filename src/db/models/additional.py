from typing import List, Optional
from datetime import date, datetime, time
from sqlalchemy import (
    Column, String, ForeignKey, Date, Time, Integer, Float,
    Boolean, Text, JSON, Numeric, Enum as SQLEnum, UniqueConstraint
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from src.db.base import Base, TimestampMixin
import enum


class BunkerStatus(str, enum.Enum):
    """Статусы бункера"""
    CLEAN = "clean"          # Чистый
    FILLED = "filled"        # Заполнен
    IN_USE = "in_use"       # В использовании
    DIRTY = "dirty"         # Грязный
    MAINTENANCE = "maintenance"  # На обслуживании


class BagStatus(str, enum.Enum):
    """Статусы сумки-комплекта"""
    PREPARING = "preparing"   # Готовится
    READY = "ready"          # Готова
    ISSUED = "issued"        # Выдана
    IN_USE = "in_use"       # Используется
    RETURNED = "returned"    # Возвращена


class MaintenanceType(str, enum.Enum):
    """Типы техобслуживания"""
    CLEANING = "cleaning"         # Чистка
    TECHNICAL = "technical"       # Техническое ТО
    REPAIR = "repair"            # Ремонт
    INSPECTION = "inspection"     # Инспекция


class Bunker(Base, TimestampMixin):
    """Модель бункера"""
    __tablename__ = "bunkers"
    
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredients.id"),
        nullable=False
    )
    
    # Вес и емкость
    empty_weight: Mapped[float] = mapped_column(Float, nullable=False)  # Вес пустого
    max_capacity: Mapped[float] = mapped_column(Float, nullable=False)  # Макс емкость
    current_weight: Mapped[Optional[float]] = mapped_column(Float)      # Текущий вес
    
    # Статус и циклы
    status: Mapped[BunkerStatus] = mapped_column(
        SQLEnum(BunkerStatus),
        default=BunkerStatus.CLEAN
    )
    use_cycles: Mapped[int] = mapped_column(Integer, default=0)         # Циклы использования
    max_cycles: Mapped[int] = mapped_column(Integer, default=10)        # Макс циклов до мойки
    
    # Локация
    current_location_type: Mapped[Optional[str]] = mapped_column(String(50))
    current_location_id: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Отношения
    ingredient: Mapped["Ingredient"] = relationship("Ingredient")
    weighings: Mapped[List["BunkerWeighing"]] = relationship(
        "BunkerWeighing",
        back_populates="bunker"
    )
    
    @property
    def net_weight(self) -> float:
        """Чистый вес содержимого"""
        if self.current_weight:
            return self.current_weight - self.empty_weight
        return 0.0
    
    @property
    def fill_percentage(self) -> float:
        """Процент заполнения"""
        if self.max_capacity > 0:
            return (self.net_weight / self.max_capacity) * 100
        return 0.0


class BunkerWeighing(Base, TimestampMixin):
    """Модель взвешивания бункера"""
    __tablename__ = "bunker_weighings"
    
    bunker_id: Mapped[int] = mapped_column(
        ForeignKey("bunkers.id"),
        nullable=False
    )
    
    # Взвешивание
    gross_weight: Mapped[float] = mapped_column(Float, nullable=False)  # Общий вес
    net_weight: Mapped[float] = mapped_column(Float, nullable=False)    # Чистый вес
    
    # Кто и когда
    weighed_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False
    )
    
    # Фото
    photo_url: Mapped[Optional[str]] = mapped_column(String(500))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    
    # Отношения
    bunker: Mapped["Bunker"] = relationship(
        "Bunker",
        back_populates="weighings"
    )
    weighed_by: Mapped["User"] = relationship("User")


class Bag(Base, TimestampMixin):
    """Модель сумки-комплекта"""
    __tablename__ = "bags"
    
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("machine_tasks.id"),
        nullable=False
    )
    
    status: Mapped[BagStatus] = mapped_column(
        SQLEnum(BagStatus),
        default=BagStatus.PREPARING
    )
    
    # Даты
    prepared_at: Mapped[Optional[datetime]] = mapped_column()
    issued_at: Mapped[Optional[datetime]] = mapped_column()
    returned_at: Mapped[Optional[datetime]] = mapped_column()
    
    # Кто собирал и кому выдали
    prepared_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id")
    )
    issued_to_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id")
    )
    
    # Отношения
    task: Mapped["MachineTask"] = relationship("MachineTask")
    prepared_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[prepared_by_id]
    )
    issued_to: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[issued_to_id]
    )
    items: Mapped[List["BagItem"]] = relationship(
        "BagItem",
        back_populates="bag",
        cascade="all, delete-orphan"
    )


class BagItem(Base):
    """Элементы сумки-комплекта"""
    __tablename__ = "bag_items"
    
    bag_id: Mapped[int] = mapped_column(
        ForeignKey("bags.id"),
        nullable=False
    )
    
    # Что положили
    item_type: Mapped[str] = mapped_column(String(50))  # bunker, ingredient, consumable
    item_id: Mapped[int] = mapped_column(Integer)       # ID соответствующей сущности
    quantity: Mapped[float] = mapped_column(Float)
    
    # Проверка
    checked_by_operator: Mapped[bool] = mapped_column(Boolean, default=False)
    check_photo_url: Mapped[Optional[str]] = mapped_column(String(500))
    
    # Отношения
    bag: Mapped["Bag"] = relationship("Bag", back_populates="items")


class Supplier(Base):
    """Модель поставщика"""
    __tablename__ = "suppliers"
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    
    # Контакты
    contact_person: Mapped[Optional[str]] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    email: Mapped[Optional[str]] = mapped_column(String(255))
    address: Mapped[Optional[str]] = mapped_column(Text)
    
    # Реквизиты
    inn: Mapped[Optional[str]] = mapped_column(String(20))
    bank_account: Mapped[Optional[str]] = mapped_column(String(50))
    
    # Статус
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    rating: Mapped[Optional[int]] = mapped_column(Integer)  # 1-5
    
    # Отношения
    purchases: Mapped[List["Purchase"]] = relationship(
        "Purchase",
        back_populates="supplier"
    )
    ingredients: Mapped[List["SupplierIngredient"]] = relationship(
        "SupplierIngredient",
        back_populates="supplier"
    )


class Purchase(Base, TimestampMixin):
    """Модель закупки"""
    __tablename__ = "purchases"
    
    supplier_id: Mapped[int] = mapped_column(
        ForeignKey("suppliers.id"),
        nullable=False
    )
    
    # Документы
    invoice_number: Mapped[Optional[str]] = mapped_column(String(100))
    invoice_date: Mapped[Optional[date]] = mapped_column(Date)
    
    # Суммы
    total_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    vat_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    
    # Статус
    status: Mapped[str] = mapped_column(String(50), default="pending")
    payment_status: Mapped[str] = mapped_column(String(50), default="unpaid")
    
    # Доставка
    delivery_date: Mapped[Optional[date]] = mapped_column(Date)
    received_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id")
    )
    
    # Отношения
    supplier: Mapped["Supplier"] = relationship(
        "Supplier",
        back_populates="purchases"
    )
    items: Mapped[List["PurchaseItem"]] = relationship(
        "PurchaseItem",
        back_populates="purchase",
        cascade="all, delete-orphan"
    )
    received_by: Mapped[Optional["User"]] = relationship("User")


class PurchaseItem(Base):
    """Позиции закупки"""
    __tablename__ = "purchase_items"
    
    purchase_id: Mapped[int] = mapped_column(
        ForeignKey("purchases.id"),
        nullable=False
    )
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredients.id"),
        nullable=False
    )
    
    # Количество и цены
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    total_price: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    
    # Приемка
    received_quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3))
    
    # Отношения
    purchase: Mapped["Purchase"] = relationship(
        "Purchase",
        back_populates="items"
    )
    ingredient: Mapped["Ingredient"] = relationship("Ingredient")


class SupplierIngredient(Base):
    """Связь поставщиков и ингредиентов"""
    __tablename__ = "supplier_ingredients"
    
    supplier_id: Mapped[int] = mapped_column(
        ForeignKey("suppliers.id"),
        nullable=False
    )
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredients.id"),
        nullable=False
    )
    
    # Условия поставки
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    min_order_quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3))
    delivery_days: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Отношения
    supplier: Mapped["Supplier"] = relationship(
        "Supplier",
        back_populates="ingredients"
    )
    ingredient: Mapped["Ingredient"] = relationship("Ingredient")
    
    __table_args__ = (
        UniqueConstraint("supplier_id", "ingredient_id"),
    )


class MaintenanceSchedule(Base):
    """График техобслуживания"""
    __tablename__ = "maintenance_schedules"
    
    machine_id: Mapped[int] = mapped_column(
        ForeignKey("machines.id"),
        nullable=False
    )
    
    # Тип и периодичность
    maintenance_type: Mapped[MaintenanceType] = mapped_column(
        SQLEnum(MaintenanceType),
        nullable=False
    )
    interval_days: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Последнее и следующее ТО
    last_maintenance_date: Mapped[Optional[date]] = mapped_column(Date)
    next_maintenance_date: Mapped[date] = mapped_column(Date, nullable=False)
    
    # Чек-лист
    checklist: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Статус
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Отношения
    machine: Mapped["Machine"] = relationship("Machine")
    history: Mapped[List["MaintenanceHistory"]] = relationship(
        "MaintenanceHistory",
        back_populates="schedule"
    )


class MaintenanceHistory(Base, TimestampMixin):
    """История техобслуживания"""
    __tablename__ = "maintenance_history"
    
    schedule_id: Mapped[int] = mapped_column(
        ForeignKey("maintenance_schedules.id"),
        nullable=False
    )
    performed_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False
    )
    
    # Выполнение
    performed_date: Mapped[date] = mapped_column(Date, nullable=False)
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Результаты
    checklist_results: Mapped[dict] = mapped_column(JSON, default=dict)
    issues_found: Mapped[Optional[str]] = mapped_column(Text)
    photos: Mapped[List[str]] = mapped_column(JSON, default=list)
    
    # Отношения
    schedule: Mapped["MaintenanceSchedule"] = relationship(
        "MaintenanceSchedule",
        back_populates="history"
    )
    performed_by: Mapped["User"] = relationship("User")


class VehicleLog(Base, TimestampMixin):
    """Журнал транспорта"""
    __tablename__ = "vehicle_logs"
    
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False
    )
    
    # Тип записи
    log_type: Mapped[str] = mapped_column(String(50))  # mileage, fuel, maintenance
    
    # Пробег
    mileage_start: Mapped[Optional[int]] = mapped_column(Integer)
    mileage_end: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Заправка
    fuel_amount: Mapped[Optional[float]] = mapped_column(Float)
    fuel_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    fuel_station: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Фото и документы
    receipt_photo: Mapped[Optional[str]] = mapped_column(String(500))
    odometer_photo: Mapped[Optional[str]] = mapped_column(String(500))
    
    # Примечания
    notes: Mapped[Optional[str]] = mapped_column(Text)
    
    # Отношения
    user: Mapped["User"] = relationship("User")


class CashCollection(Base, TimestampMixin):
    """Инкассация наличных"""
    __tablename__ = "cash_collections"
    
    machine_id: Mapped[int] = mapped_column(
        ForeignKey("machines.id"),
        nullable=False
    )
    collected_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False
    )
    
    # Суммы
    amount_declared: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    amount_verified: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    
    # Купюры
    bills_photo: Mapped[Optional[str]] = mapped_column(String(500))
    bills_breakdown: Mapped[dict] = mapped_column(JSON, default=dict)  # {1000: 5, 5000: 2, ...}
    
    # Верификация
    verified_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id")
    )
    verified_at: Mapped[Optional[datetime]] = mapped_column()
    discrepancy_notes: Mapped[Optional[str]] = mapped_column(Text)
    
    # Отношения
    machine: Mapped["Machine"] = relationship("Machine")
    collected_by: Mapped["User"] = relationship(
        "User",
        foreign_keys=[collected_by_id]
    )
    verified_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[verified_by_id]
    )