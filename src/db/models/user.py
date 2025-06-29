from typing import List, Optional
from datetime import datetime
from sqlalchemy import (
    Boolean, Column, String, BigInteger, DateTime, 
    Table, ForeignKey, JSON, UniqueConstraint
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from src.db.base import Base, SoftDeleteMixin, UUIDMixin


# Таблица связи многие-ко-многим для пользователей и ролей
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("assigned_at", DateTime, default=datetime.utcnow),
    Column("assigned_by", ForeignKey("users.id")),
)


class User(Base, UUIDMixin, SoftDeleteMixin):
    """Модель пользователя"""
    __tablename__ = "users"

    # Основные поля
    telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), unique=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(100), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Статусы
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    # Настройки пользователя (язык, тема, уведомления и т.д.)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Отношения
    roles: Mapped[List["Role"]] = relationship(
        "Role",
        secondary=user_roles,
        back_populates="users",
        lazy="selectin"
    )
    
    # Машины, за которые отвечает
    managed_machines: Mapped[List["Machine"]] = relationship(
        "Machine",
        back_populates="responsible_user",
        foreign_keys="Machine.responsible_user_id"
    )
    
    # Задачи оператора
    assigned_tasks: Mapped[List["MachineTask"]] = relationship(
        "MachineTask",
        back_populates="assigned_to",
        foreign_keys="MachineTask.assigned_to_id"
    )
    
    # Инвестиции
    investments: Mapped[List["MachineInvestor"]] = relationship(
        "MachineInvestor",
        back_populates="investor"
    )
    
    # Созданные транзакции
    created_transactions: Mapped[List["FinanceTransaction"]] = relationship(
        "FinanceTransaction",
        back_populates="created_by"
    )

    def __repr__(self):
        return f"<User {self.username or self.full_name}>"

    @property
    def display_name(self) -> str:
        """Отображаемое имя"""
        return self.full_name or self.username or f"User {self.id}"

    def has_role(self, role_name: str) -> bool:
        """Проверка наличия роли"""
        return any(role.name == role_name for role in self.roles)

    def has_any_role(self, role_names: List[str]) -> bool:
        """Проверка наличия любой из ролей"""
        user_roles = {role.name for role in self.roles}
        return bool(user_roles.intersection(role_names))

    def has_permission(self, module: str, action: str) -> bool:
        """Проверка разрешения"""
        for role in self.roles:
            for perm in role.permissions:
                if perm.module == module and perm.action == action:
                    return True
        return False


class Role(Base):
    """Модель роли"""
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(String)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Отношения
    users: Mapped[List["User"]] = relationship(
        "User",
        secondary=user_roles,
        back_populates="roles"
    )
    
    permissions: Mapped[List["Permission"]] = relationship(
        "Permission",
        secondary="role_permissions",
        back_populates="roles"
    )

    def __repr__(self):
        return f"<Role {self.name}>"


# Таблица связи ролей и разрешений
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


class Permission(Base):
    """Модель разрешения"""
    __tablename__ = "permissions"

    module: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String)
    
    # Отношения
    roles: Mapped[List["Role"]] = relationship(
        "Role",
        secondary=role_permissions,
        back_populates="permissions"
    )

    __table_args__ = (
        UniqueConstraint("module", "action", name="uq_permission_module_action"),
    )

    def __repr__(self):
        return f"<Permission {self.module}:{self.action}>"
