from typing import List, Optional
from datetime import datetime
from sqlalchemy import (
    Column, String, ForeignKey, Numeric, JSON,
    Text, Enum as SQLEnum, Index, CheckConstraint
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from src.db.base import Base, TimestampMixin, UUIDMixin
import enum


class AccountType(str, enum.Enum):
    """Типы счетов"""
    CASH = "cash"           # Наличные
    BANK = "bank"           # Банковский счет
    WALLET = "wallet"       # Электронный кошелек
    CARD = "card"           # Карта


class TransactionType(str, enum.Enum):
    """Типы транзакций"""
    INCOME = "income"       # Доход
    EXPENSE = "expense"     # Расход
    TRANSFER = "transfer"   # Перевод


class TransactionCategory(str, enum.Enum):
    """Категории транзакций"""
    # Доходы
    SALES = "sales"                     # Продажи
    INVESTMENT = "investment"           # Инвестиции
    OTHER_INCOME = "other_income"       # Прочие доходы
    
    # Расходы
    PURCHASE = "purchase"               # Закупка товаров
    RENT = "rent"                      # Аренда
    UTILITIES = "utilities"            # Коммуналка
    SALARY = "salary"                  # Зарплата
    TRANSPORT = "transport"            # Транспорт
    REPAIR = "repair"                  # Ремонт
    COMMUNICATION = "communication"    # Связь
    MARKETING = "marketing"            # Маркетинг
    TAX = "tax"                       # Налоги
    OTHER_EXPENSE = "other_expense"    # Прочие расходы
    
    # Специальные
    COLLECTION = "collection"          # Инкассация
    ADJUSTMENT = "adjustment"          # Корректировка


class PaymentMethod(str, enum.Enum):
    """Способы оплаты"""
    CASH = "cash"
    PAYME = "payme"
    CLICK = "click"
    UZUM = "uzum"
    BANK_TRANSFER = "bank_transfer"
    CARD = "card"
    OTHER = "other"


class FinanceAccount(Base):
    """Модель финансового счета"""
    __tablename__ = "finance_accounts"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[AccountType] = mapped_column(SQLEnum(AccountType), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="UZS")
    balance: Mapped[float] = mapped_column(Numeric(15, 2), default=0)
    is_active: Mapped[bool] = mapped_column(default=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Отношения
    transactions_from: Mapped[List["FinanceTransaction"]] = relationship(
        "FinanceTransaction",
        foreign_keys="FinanceTransaction.from_account_id",
        back_populates="from_account"
    )
    
    transactions_to: Mapped[List["FinanceTransaction"]] = relationship(
        "FinanceTransaction",
        foreign_keys="FinanceTransaction.to_account_id",
        back_populates="to_account"
    )

    def __repr__(self):
        return f"<Account {self.code}: {self.name} ({self.balance} {self.currency})>"

    @property
    def formatted_balance(self) -> str:
        """Форматированный баланс"""
        return f"{self.balance:,.2f} {self.currency}"


class FinanceTransaction(Base, UUIDMixin, TimestampMixin):
    """Модель финансовой транзакции"""
    __tablename__ = "finance_transactions"

    type: Mapped[TransactionType] = mapped_column(
        SQLEnum(TransactionType), 
        nullable=False,
        index=True
    )
    category: Mapped[Optional[TransactionCategory]] = mapped_column(
        SQLEnum(TransactionCategory),
        index=True
    )
    
    # Счета
    from_account_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("finance_accounts.id", ondelete="RESTRICT")
    )
    to_account_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("finance_accounts.id", ondelete="RESTRICT")
    )
    
    # Сумма и описание
    amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # Ссылки на связанные объекты
    reference_type: Mapped[Optional[str]] = mapped_column(String(50))
    reference_id: Mapped[Optional[int]] = mapped_column()
    
    # Создатель
    created_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    
    # Вложения и метаданные
    attachments: Mapped[list] = mapped_column(JSON, default=list)
    metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Отношения
    from_account: Mapped[Optional["FinanceAccount"]] = relationship(
        "FinanceAccount",
        foreign_keys=[from_account_id],
        back_populates="transactions_from"
    )
    
    to_account: Mapped[Optional["FinanceAccount"]] = relationship(
        "FinanceAccount",
        foreign_keys=[to_account_id],
        back_populates="transactions_to"
    )
    
    created_by: Mapped[Optional["User"]] = relationship("User")

    __table_args__ = (
        CheckConstraint(
            "(type = 'transfer' AND from_account_id IS NOT NULL AND to_account_id IS NOT NULL) OR "
            "(type = 'income' AND from_account_id IS NULL AND to_account_id IS NOT NULL) OR "
            "(type = 'expense' AND from_account_id IS NOT NULL AND to_account_id IS NULL)",
            name="check_transaction_accounts"
        ),
        CheckConstraint("amount > 0", name="check_positive_amount"),
        Index("idx_finance_date", "action_timestamp"),
        Index("idx_finance_category", "category"),
        Index("idx_finance_reference", "reference_type", "reference_id"),
    )

    def __repr__(self):
        return f"<Transaction {self.type}: {self.amount} on {self.action_timestamp}>"


class Sale(Base, UUIDMixin, TimestampMixin):
    """Модель продажи"""
    __tablename__ = "sales"

    machine_id: Mapped[int] = mapped_column(
        ForeignKey("machines.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False
    )
    
    # Детали продажи
    quantity: Mapped[int] = mapped_column(default=1)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    
    # Оплата
    payment_method: Mapped[Optional[PaymentMethod]] = mapped_column(
        SQLEnum(PaymentMethod)
    )
    transaction_id: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Синхронизация
    sync_status: Mapped[str] = mapped_column(
        String(50), 
        default="pending",
        index=True
    )
    raw_data: Mapped[Optional[dict]] = mapped_column(JSON)
    
    # Отношения
    machine: Mapped["Machine"] = relationship("Machine", back_populates="sales")
    product: Mapped["Product"] = relationship("Product", back_populates="sales")
    payments: Mapped[List["Payment"]] = relationship(
        "Payment",
        back_populates="sale",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_sales_machine_date", "machine_id", "action_timestamp"),
        Index("idx_sales_sync", "sync_status"),
    )

    def __repr__(self):
        return f"<Sale {self.product.name} x{self.quantity} = {self.total_amount}>"


class Payment(Base):
    """Модель платежа (для сверки)"""
    __tablename__ = "payments"

    sale_id: Mapped[int] = mapped_column(
        ForeignKey("sales.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Источник данных
    source: Mapped[str] = mapped_column(String(50), nullable=False)  # machine, multicassa, payme, etc
    external_id: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Детали платежа
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    payment_method: Mapped[PaymentMethod] = mapped_column(SQLEnum(PaymentMethod))
    payment_date: Mapped[datetime] = mapped_column(nullable=False)
    
    # Статус сверки
    is_verified: Mapped[bool] = mapped_column(default=False)
    verified_at: Mapped[Optional[datetime]] = mapped_column()
    verification_notes: Mapped[Optional[str]] = mapped_column(Text)
    
    # Сырые данные
    raw_data: Mapped[Optional[dict]] = mapped_column(JSON)
    
    # Отношения
    sale: Mapped["Sale"] = relationship("Sale", back_populates="payments")

    __table_args__ = (
        Index("idx_payment_source", "source", "external_id"),
        Index("idx_payment_verification", "is_verified"),
    )

    def __repr__(self):
        return f"<Payment {self.amount} from {self.source}>"


class ExpenseBudget(Base):
    """Модель бюджета расходов"""
    __tablename__ = "expense_budgets"

    category: Mapped[TransactionCategory] = mapped_column(
        SQLEnum(TransactionCategory),
        nullable=False
    )
    year: Mapped[int] = mapped_column(nullable=False)
    month: Mapped[int] = mapped_column(nullable=False)
    planned_amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    actual_amount: Mapped[float] = mapped_column(Numeric(15, 2), default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    __table_args__ = (
        Index("idx_budget_period", "year", "month", "category", unique=True),
    )

    @property
    def variance(self) -> float:
        """Отклонение от бюджета"""
        return float(self.actual_amount - self.planned_amount)

    @property
    def variance_percent(self) -> float:
        """Процент отклонения"""
        if self.planned_amount == 0:
            return 0
        return (self.variance / float(self.planned_amount)) * 100