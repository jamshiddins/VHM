from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy import Column, DateTime, Integer, func
from sqlalchemy.ext.declarative import as_declarative, declared_attr
from sqlalchemy.dialects.postgresql import UUID
import uuid

@as_declarative()
class Base:
    """Базовый класс для всех моделей"""
    id: Any
    __name__: str
    
    # Автогенерация имени таблицы
    @declared_attr
    def __tablename__(cls) -> str:
        return cls.__name__.lower() + "s"
    
    # Общие поля для всех таблиц
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


class TimestampMixin:
    """Миксин для исторических данных"""
    action_timestamp = Column(DateTime, nullable=False, index=True)
    entry_timestamp = Column(DateTime, default=func.now(), nullable=False)


class SoftDeleteMixin:
    """Миксин для мягкого удаления"""
    deleted_at = Column(DateTime, nullable=True, index=True)
    
    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
    
    def soft_delete(self):
        self.deleted_at = datetime.utcnow()
    
    def restore(self):
        self.deleted_at = None


class UUIDMixin:
    """Миксин для публичных UUID"""
    uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False, index=True)
