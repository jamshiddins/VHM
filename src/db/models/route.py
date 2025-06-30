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
    """Статусы маршрута"""
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskType(str, enum.Enum):
    """Типы задач"""
    REFILL = "refill"               # Пополнение
    CLEANING = "cleaning"           # Чистка
    MAINTENANCE = "maintenance"     # Техобслуживание
    COLLECTION = "collection"       # Инкассация
    INSPECTION = "inspection"       # Инспекция
    REPAIR = "repair"              # Ремонт


class TaskStatus(str, enum.Enum):
    """Статусы задач"""
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ProblemType(str, enum.Enum):
    """Типы проблем"""
    NO_WATER = "no_water"
    NO_ELECTRICITY = "no_electricity"
    MACHINE_BROKEN = "machine_broken"
    NO_INGREDIENTS = "no_ingredients"
    PAYMENT_ISSUE = "payment_issue"
    ACCESS_ISSUE = "access_issue"
    OTHER = "other"


class Route(Base):
    """Модель маршрута"""
    __tablename__ = "routes"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    
    # Время и статус
    planned_start: Mapped[Optional[time]] = mapped_column(Time)
    planned_end: Mapped[Optional[time]] = mapped_column(Time)
    actual_start: Mapped[Optional[datetime]] = mapped_column()
    actual_end: Mapped[Optional[datetime]] = mapped_column()
    status: Mapped[RouteStatus] = mapped_column(
        SQLEnum(RouteStatus),
        default=RouteStatus.PLANNED,
        index=True
    )
    
    # Назначенный оператор
    assigned_to_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    
    # Дополнительная информация
    notes: Mapped[Optional[str]] = mapped_column(Text)
    metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Отношения
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
        """Количество автоматов в маршруте"""
        return len(self.machine_routes)

    @property
    def completed_tasks(self) -> int:
        """Количество выполненных задач"""
        return sum(1 for task in self.tasks if task.status == TaskStatus.COMPLETED)

    @property
    def completion_percent(self) -> float:
        """Процент выполнения"""
        if not self.tasks:
            return 0
        return (self.completed_tasks / len(self.tasks)) * 100


class MachineRoute(Base):
    """Связь автомата с маршрутом"""
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
    
    # Отношения
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
    """Модель задачи для автомата"""
    __tablename__ = "machine_tasks"

    machine_id: Mapped[int] = mapped_column(
        ForeignKey("machines.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    route_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("routes.id", ondelete="SET NULL")
    )
    
    # Тип и статус
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
    
    # Назначение
    assigned_to_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    assigned_at: Mapped[Optional[datetime]] = mapped_column()
    
    # Выполнение
    started_at: Mapped[Optional[datetime]] = mapped_column()
    completed_at: Mapped[Optional[datetime]] = mapped_column()
    
    # Детали задачи
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer, default=1)
    
    # Результаты
    result_data: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Отношения
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
    """Элементы задачи (ингредиенты для пополнения)"""
    __tablename__ = "task_items"

    task_id: Mapped[int] = mapped_column(
        ForeignKey("machine_tasks.id", ondelete="CASCADE"),
        nullable=False
    )
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredients.id", ondelete="RESTRICT"),
        nullable=False
    )
    
    # Количества
    planned_quantity: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False)
    actual_quantity: Mapped[Optional[float]] = mapped_column(Numeric(10, 3))
    returned_quantity: Mapped[Optional[float]] = mapped_column(Numeric(10, 3))
    
    # Отношения
    task: Mapped["MachineTask"] = relationship(
        "MachineTask",
        back_populates="items"
    )
    ingredient: Mapped["Ingredient"] = relationship("Ingredient")


class TaskPhoto(Base):
    """Фотографии задачи"""
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
    
    # Отношения
    task: Mapped["MachineTask"] = relationship(
        "MachineTask",
        back_populates="photos"
    )


class TaskProblem(Base):
    """Проблемы, обнаруженные при выполнении задачи"""
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
    
    # Отношения
    task: Mapped["MachineTask"] = relationship(
        "MachineTask",
        back_populates="problems"
    )