# Импорт всех моделей для корректной работы Alembic
from .user import User, Role, Permission, user_roles, role_permissions
from .machine import Machine, MachineType, MachineStatus  
from .inventory import Ingredient, Warehouse, Inventory, IngredientCategory, IngredientUnit, LocationType
from .finance import FinanceAccount, FinanceTransaction, Sale, Payment, ExpenseBudget, AccountType, TransactionType, TransactionCategory, PaymentMethod
from .recipe import Product, Recipe, RecipeIngredient, CostCalculation, ProductCategory
from .route import Route, MachineRoute, MachineTask, TaskItem, TaskPhoto, TaskProblem, RouteStatus, TaskType, TaskStatus, ProblemType
from .investment import MachineInvestor, InvestorPayout, InvestmentOffer, InvestmentReport, InvestmentStatus, PayoutStatus, OfferType, OfferStatus

__all__ = [
    # User models
    "User", "Role", "Permission", "user_roles", "role_permissions",
    
    # Machine models
    "Machine", "MachineType", "MachineStatus",
    
    # Inventory models  
    "Ingredient", "Warehouse", "Inventory", 
    "IngredientCategory", "IngredientUnit", "LocationType",
    
    # Finance models
    "FinanceAccount", "FinanceTransaction", "Sale", "Payment", "ExpenseBudget",
    "AccountType", "TransactionType", "TransactionCategory", "PaymentMethod",
    
    # Recipe models
    "Product", "Recipe", "RecipeIngredient", "CostCalculation", "ProductCategory",
    
    # Route models
    "Route", "MachineRoute", "MachineTask", "TaskItem", "TaskPhoto", "TaskProblem",
    "RouteStatus", "TaskType", "TaskStatus", "ProblemType",
    
    # Investment models
    "MachineInvestor", "InvestorPayout", "InvestmentOffer", "InvestmentReport",
    "InvestmentStatus", "PayoutStatus", "OfferType", "OfferStatus"
]
