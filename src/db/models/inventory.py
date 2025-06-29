from typing import Optional
from datetime import date, datetime
from sqlalchemy import (
    Column, String, ForeignKey, Date, Numeric, 
    Integer, Text, Enum as SQLEnum, Index
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from src.db.base import Base, TimestampMixin
import enum


class IngredientCategory(str, enum.Enum):
    """Категории ингредиентов"""
    COFFEE = "coffee"
    MILK = "milk"
    SYRUP = "syrup"
    WATER = "water"
    CUP = "cup"
    LID = "lid"
    STRAW = "straw"
    SUGAR = "sugar"
    SNACK = "snack"
    OTHER = "other"


class IngredientUnit(str, enum.Enum):
    """Единицы измерения"""
    KG = "kg"
    L = "l"
    PCS = "pcs"
    PACK = "pack"


class LocationType(str, enum.Enum):
    """Типы локаций для остатков"""
    WAREHOUSE = "warehouse"
    MACHINE = "machine"
    BAG = "bag"
    TRANSIT = "transit"


class Ingredient(Base):
    """Модель ингредиента"""
    __tablename__ = "ingredients"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[IngredientCategory] = mapped_column(
        SQLEnum(IngredientCategory),
        default=IngredientCategory.OTHER
    )
    unit: Mapped[IngredientUnit] = mapped_column(SQLEnum(IngredientUnit), nullable=False)
    cost_per_unit: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    min_stock_level: Mapped[Optional[float]] = mapped_column(Numeric(10, 3))
    barcode: Mapped[Optional[str]] = mapped_column(String(100))
    supplier_info: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Отношения
    inventory_records: Mapped[List["Inventory"]] = relationship(
        "Inventory",
        back_populates="ingredient"
    )
    
    recipe_ingredients: Mapped[List["RecipeIngredient"]] = relationship(
        "RecipeIngredient",
        back_populates="ingredient"
    )

    def __repr__(self):
        return f"<Ingredient {self.code}: {self.name}>"


class Warehouse(Base):
    """Модель склада"""
    __tablename__ = "warehouses"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[Optional[str]] = mapped_column(String)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Отношения
    inventory: Mapped[List["Inventory"]] = relationship(
        "Inventory",
        primaryjoin="and_(Warehouse.id==Inventory.location_id, Inventory.location_type=='warehouse')",
        viewonly=True
    )

    def __repr__(self):
        return f"<Warehouse {self.code}: {self.name}>"


class Inventory(Base, TimestampMixin):
    """Модель остатков"""
    __tablename__ = "inventory"

    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredients.id", ondelete="CASCADE"),
        nullable=False
    )
    location_type: Mapped[LocationType] = mapped_column(
        SQLEnum(LocationType),
        nullable=False,
        index=True
    )
    location_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    quantity: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False)
    batch_number: Mapped[Optional[str]] = mapped_column(String(100))
    expiry_date: Mapped[Optional[date]] = mapped_column(Date)
    created_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    notes: Mapped[Optional[str]] = mapped_column(Text)
    
    # Отношения
    ingredient: Mapped["Ingredient"] = relationship(
        "Ingredient",
        back_populates="inventory_records"
    )
    
    created_by: Mapped[Optional["User"]] = relationship("User")

    __table_args__ = (
        Index("idx_inventory_location", "location_type", "location_id"),
        Index("idx_inventory_timestamp", "action_timestamp"),
        Index(
            "idx_inventory_current",
            "location_type", "location_id", "ingredient_id", "action_timestamp"
        ),
    )

    def __repr__(self):
        return f"<Inventory {self.ingredient.name}: {self.quantity} {self.ingredient.unit}>"

    @property
    def location_name(self) -> str:
        """Название локации"""
        if self.location_type == LocationType.WAREHOUSE:
            # Здесь нужно будет получить название склада
            return f"Склад #{self.location_id}"
        elif self.location_type == LocationType.MACHINE:
            # Здесь нужно будет получить код автомата
            return f"Автомат #{self.location_id}"
        elif self.location_type == LocationType.BAG:
            return f"Сумка задачи #{self.location_id}"
        return f"{self.location_type} #{self.location_id}"