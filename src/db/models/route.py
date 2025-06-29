from typing import List, Optional
from datetime import date, datetime, time
from sqlalchemy import (
    Column, String, ForeignKey, Date, Time, Integer,
    Boolean, Text, JSON, Enum as SQLEnum, Index
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from src.db.base import Base, UUIDMixin
import enum


class RouteStatus(str, enum.Enum):
    """РЎС‚Р°С‚СѓСЃС‹ РјР°СЂС€СЂСѓС‚Р°"""
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskType(str, enum.Enum):
    """РўРёРїС‹ Р·Р°РґР°С‡"""
    REFILL = "refill"               # РџРѕРїРѕР»РЅРµРЅРёРµ
    CLEANING = "cleaning"           # Р§РёСЃС‚РєР°
    MAINTENANCE = "maintenance"     # РўРµС…РѕР±СЃР»СѓР¶РёРІР°РЅРёРµ
    COLLECTION = "collection"       # РРЅРєР°СЃСЃР°С†РёСЏ
    INSPECTION = "inspection"       # РРЅСЃРїРµРєС†РёСЏ
    REPAIR = "repair"              # Р РµРјРѕРЅС‚


class TaskStatus(str, enum.Enum):
    """РЎС‚Р°С‚СѓСЃС‹ Р·Р°РґР°С‡"""
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ProblemType(str, enum.Enum):
    """РўРёРїС‹ РїСЂРѕР±Р»РµРј"""
    NO_WATER = "no_water"
    NO_ELECTRICITY = "no_electricity"
    MACHINE_BROKEN = "machine_broken"
    NO_INGREDIENTS = "no_ingredients"
    PAYMENT_ISSUE = "payment_issue"
    ACCESS_ISSUE = "access_issue"
    OTHER = "other"


class Route(Base):
    """РњРѕРґРµР»СЊ РјР°СЂС€СЂСѓС‚Р°"""
    __tablename__ = "routes"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    
    # Р’СЂРµРјСЏ Рё СЃС‚Р°С‚СѓСЃ
    planned_start: Mapped[Optional[time]] = mapped_column(Time)
    planned_end: Mapped[Optional[time]] = mapped_column(Time)
    actual_start: Mapped[Optional[datetime]] = mapped_column()
    actual_end: Mapped[Optional[datetime]] = mapped_column()
    status: Mapped[RouteStatus] = mapped_column(
        SQLEnum(RouteStatus),
        default=RouteStatus.PLANNED,
        index=True
    )
    
    # РќР°Р·РЅР°С‡РµРЅРЅС‹Р№ РѕРїРµСЂР°С‚РѕСЂ
    assigned_to_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    
    # Р”РѕРїРѕР»РЅРёС‚РµР»СЊРЅР°СЏ РёРЅС„РѕСЂРјР°С†РёСЏ
    notes: Mapped[Optional[str]] = mapped_column(Text)
    metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # РћС‚РЅРѕС€РµРЅРёСЏ
    assigned_to: Mapped[Optional["User"]] = relationship("User")
    machine_routes: Mapped[List["MachineRoute"]] = relationship(
        "MachineRoute",
        back_populates="route",
        cascade="all, delete-orphan"
    )
    tasks: Mapped[List["MachineTask"]] = relationship(
        "MachineTask",
        back_populates="route"
    )

    def __repr__(self):
        return f"<Route {self.name} on {self.date}>"

    @property
    def machine_count(self) -> int:
        """РљРѕР»РёС‡РµСЃС‚РІРѕ Р°РІС‚РѕРјР°С‚РѕРІ РІ РјР°СЂС€СЂСѓС‚Рµ"""
        return len(self.machine_routes)

    @property
    def completed_tasks(self) -> int:
        """РљРѕР»РёС‡РµСЃС‚РІРѕ РІС‹РїРѕР»РЅРµРЅРЅС‹С… Р·Р°РґР°С‡"""
        return sum(1 for task in self.tasks if task.status == TaskStatus.COMPLETED)

    @property
    def completion_percent(self) -> float:
        """РџСЂРѕС†РµРЅС‚ РІС‹РїРѕР»РЅРµРЅРёСЏ"""
        if not self.tasks:
            return 0
        return (self.completed_tasks / len(self.tasks)) * 100


class MachineRoute(Base):
    """РЎРІСЏР·СЊ Р°РІС‚РѕРјР°С‚Р° СЃ РјР°СЂС€СЂСѓС‚РѕРј"""
    __tablename__ = "machine_routes"

    route_id: Mapped[int] = mapped_column(
        ForeignKey("routes.id", ondelete="CASCADE"),
        nullable=False
    )
    machine_id: Mapped[int] = mapped_column(
        ForeignKey("machines.id", ondelete="CASCADE"),
        nullable=False
    )
    sequence_number: Mapped[int] = mapped_column(Integer, default=1)
    
    # РћС‚РЅРѕС€РµРЅРёСЏ
    route: Mapped["Route"] = relationship(
        "Route",
        back_populates="machine_routes"
    )
    machine: Mapped["Machine"] = relationship(
        "Machine",
        back_populates="routes"
    )

    __table_args__ = (
        Index("idx_machine_route", "route_id", "machine_id", unique=True),
        Index("idx_route_sequence", "route_id", "sequence_number"),
    )


class MachineTask(Base, UUIDMixin):
    """РњРѕРґРµР»СЊ Р·Р°РґР°С‡Рё РґР»СЏ Р°РІС‚РѕРјР°С‚Р°"""
    __tablename__ = "machine_tasks"

    machine_id: Mapped[int] = mapped_column(
        ForeignKey("machines.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    route_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("routes.id", ondelete="SET NULL")
    )
    
    # РўРёРї Рё СЃС‚Р°С‚СѓСЃ
    type: Mapped[TaskType] = mapped_column(
        SQLEnum(TaskType),
        nullable=False,
        index=True
    )
    status: Mapped[TaskStatus] = mapped_column(
        SQLEnum(TaskStatus),
        default=TaskStatus.PENDING,
        index=True
    )
    
    # РќР°Р·РЅР°С‡РµРЅРёРµ
    assigned_to_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    assigned_at: Mapped[Optional[datetime]] = mapped_column()
    
    # Р’С‹РїРѕР»РЅРµРЅРёРµ
    started_at: Mapped[Optional[datetime]] = mapped_column()
    completed_at: Mapped[Optional[datetime]] = mapped_column()
    
    # Р”РµС‚Р°Р»Рё Р·Р°РґР°С‡Рё
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer, default=1)
    
    # Р РµР·СѓР»СЊС‚Р°С‚С‹
    result_data: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # РћС‚РЅРѕС€РµРЅРёСЏ
    machine: Mapped["Machine"] = relationship(
        "Machine",
        back_populates="tasks"
    )
    route: Mapped[Optional["Route"]] = relationship(
        "Route",
        back_populates="tasks"
    )
    assigned_to: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="assigned_tasks"
    )
    
    items: Mapped[List["TaskItem"]] = relationship(
        "TaskItem",
        back_populates="task",
        cascade="all, delete-orphan"
    )
    
    photos: Mapped[List["TaskPhoto"]] = relationship(
        "TaskPhoto",
        back_populates="task",
        cascade="all, delete-orphan"
    )
    
    problems: Mapped[List["TaskProblem"]] = relationship(
        "TaskProblem",
        back_populates="task",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Task {self.type} for {self.machine.code}>"


class TaskItem(Base):
    """Р­Р»РµРјРµРЅС‚С‹ Р·Р°РґР°С‡Рё (РёРЅРіСЂРµРґРёРµРЅС‚С‹ РґР»СЏ РїРѕРїРѕР»РЅРµРЅРёСЏ)"""
    __tablename__ = "task_items"

    task_id: Mapped[int] = mapped_column(
        ForeignKey("machine_tasks.id", ondelete="CASCADE"),
        nullable=False
    )
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredients.id", ondelete="RESTRICT"),
        nullable=False
    )
    
    # РљРѕР»РёС‡РµСЃС‚РІР°
    planned_quantity: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False)
    actual_quantity: Mapped[Optional[float]] = mapped_column(Numeric(10, 3))
    returned_quantity: Mapped[Optional[float]] = mapped_column(Numeric(10, 3))
    
    # РћС‚РЅРѕС€РµРЅРёСЏ
    task: Mapped["MachineTask"] = relationship(
        "MachineTask",
        back_populates="items"
    )
    ingredient: Mapped["Ingredient"] = relationship("Ingredient")


class TaskPhoto(Base):
    """Р¤РѕС‚РѕРіСЂР°С„РёРё Р·Р°РґР°С‡Рё"""
    __tablename__ = "task_photos"

    task_id: Mapped[int] = mapped_column(
        ForeignKey("machine_tasks.id", ondelete="CASCADE"),
        nullable=False
    )
    
    photo_type: Mapped[str] = mapped_column(String(50), nullable=False)  # before, after, problem
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    telegram_file_id: Mapped[Optional[str]] = mapped_column(String(255))
    caption: Mapped[Optional[str]] = mapped_column(String(500))
    uploaded_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    
    # РћС‚РЅРѕС€РµРЅРёСЏ
    task: Mapped["MachineTask"] = relationship(
        "MachineTask",
        back_populates="photos"
    )


class TaskProblem(Base):
    """РџСЂРѕР±Р»РµРјС‹, РѕР±РЅР°СЂСѓР¶РµРЅРЅС‹Рµ РїСЂРё РІС‹РїРѕР»РЅРµРЅРёРё Р·Р°РґР°С‡Рё"""
    __tablename__ = "task_problems"

    task_id: Mapped[int] = mapped_column(
        ForeignKey("machine_tasks.id", ondelete="CASCADE"),
        nullable=False
    )
    
    problem_type: Mapped[ProblemType] = mapped_column(
        SQLEnum(ProblemType),
        nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    is_critical: Mapped[bool] = mapped_column(Boolean, default=False)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column()
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text)
    
    # РћС‚РЅРѕС€РµРЅРёСЏ
    task: Mapped["MachineTask"] = relationship(
        "MachineTask",
        back_populates="problems"
    )
