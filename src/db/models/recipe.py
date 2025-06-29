from typing import List, Optional
from datetime import datetime
from sqlalchemy import (
    Column, String, ForeignKey, Numeric, Boolean,
    Integer, UniqueConstraint, CheckConstraint, Index,
    Enum as SQLEnum
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from src.db.base import Base
import enum


class ProductCategory(str, enum.Enum):
    """Категории продуктов"""
    COFFEE = "coffee"
    TEA = "tea"
    CHOCOLATE = "chocolate"
    SNACK = "snack"
    WATER = "water"
    JUICE = "juice"
    OTHER = "other"


class Product(Base):
    """Модель продукта"""
    __tablename__ = "products"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[Optional[ProductCategory]] = mapped_column(
        SQLEnum(ProductCategory),
        index=True
    )
    
    # Цены и налоги
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    vat_rate: Mapped[float] = mapped_column(Numeric(4, 2), default=0.12)
    
    # Статус
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    
    # Дополнительная информация
    description: Mapped[Optional[str]] = mapped_column(String)
    image_url: Mapped[Optional[str]] = mapped_column(String)
    barcode: Mapped[Optional[str]] = mapped_column(String(100))
    
    # Отношения
    recipes: Mapped[List["Recipe"]] = relationship(
        "Recipe",
        back_populates="product",
        cascade="all, delete-orphan"
    )
    
    sales: Mapped[List["Sale"]] = relationship(
        "Sale",
        back_populates="product"
    )

    def __repr__(self):
        return f"<Product {self.code}: {self.name} ({self.price})>"

    @property
    def price_without_vat(self) -> float:
        """Цена без НДС"""
        return float(self.price) / (1 + float(self.vat_rate))

    @property
    def vat_amount(self) -> float:
        """Сумма НДС"""
        return float(self.price) - self.price_without_vat

    @property
    def active_recipe(self) -> Optional["Recipe"]:
        """Активный рецепт"""
        for recipe in self.recipes:
            if recipe.is_active:
                return recipe
        return None


class Recipe(Base):
    """Модель рецепта"""
    __tablename__ = "recipes"

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[Optional[str]] = mapped_column(String)
    
    # Отношения
    product: Mapped["Product"] = relationship(
        "Product",
        back_populates="recipes"
    )
    
    ingredients: Mapped[List["RecipeIngredient"]] = relationship(
        "RecipeIngredient",
        back_populates="recipe",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("product_id", "version", name="uq_recipe_product_version"),
        # Только один активный рецепт на продукт
        UniqueConstraint(
            "product_id", "is_active",
            name="uq_recipe_active",
            postgresql_where="is_active = true"
        ),
    )

    def __repr__(self):
        return f"<Recipe for {self.product.name} v{self.version}>"

    @property
    def total_cost(self) -> float:
        """Общая себестоимость по рецепту"""
        cost = 0
        for item in self.ingredients:
            if item.ingredient.cost_per_unit:
                cost += float(item.quantity) * float(item.ingredient.cost_per_unit)
        return cost

    @property
    def ingredient_list(self) -> dict:
        """Список ингредиентов с количеством"""
        return {
            item.ingredient.name: {
                "quantity": float(item.quantity),
                "unit": item.ingredient.unit,
                "cost": float(item.quantity) * float(item.ingredient.cost_per_unit or 0)
            }
            for item in self.ingredients
        }


class RecipeIngredient(Base):
    """Модель ингредиента в рецепте"""
    __tablename__ = "recipe_ingredients"

    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"),
        nullable=False
    )
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredients.id", ondelete="RESTRICT"),
        nullable=False
    )
    quantity: Mapped[float] = mapped_column(
        Numeric(10, 3),
        nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(String)
    
    # Отношения
    recipe: Mapped["Recipe"] = relationship(
        "Recipe",
        back_populates="ingredients"
    )
    
    ingredient: Mapped["Ingredient"] = relationship(
        "Ingredient",
        back_populates="recipe_ingredients"
    )

    __table_args__ = (
        UniqueConstraint("recipe_id", "ingredient_id", name="uq_recipe_ingredient"),
        CheckConstraint("quantity > 0", name="check_positive_quantity"),
    )

    def __repr__(self):
        return f"<RecipeIngredient {self.ingredient.name}: {self.quantity}>"


class CostCalculation(Base):
    """Модель расчета себестоимости"""
    __tablename__ = "cost_calculations"

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False
    )
    machine_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("machines.id", ondelete="CASCADE")
    )
    
    # Компоненты себестоимости
    ingredient_cost: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    rent_cost: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    utilities_cost: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    salary_cost: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    other_cost: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    
    # Итоговая себестоимость
    total_cost: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    
    # Период расчета
    calculation_date: Mapped[datetime] = mapped_column(nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Отношения
    product: Mapped["Product"] = relationship("Product")
    machine: Mapped[Optional["Machine"]] = relationship("Machine")

    __table_args__ = (
        Index("idx_cost_current", "product_id", "machine_id", "is_current"),
    )

    @property
    def margin(self) -> float:
        """Маржа"""
        if self.product.price == 0:
            return 0
        return float(self.product.price - self.total_cost)

    @property
    def margin_percent(self) -> float:
        """Процент маржи"""
        if self.product.price == 0:
            return 0
        return (self.margin / float(self.product.price)) * 100
