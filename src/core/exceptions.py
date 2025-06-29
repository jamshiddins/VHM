from typing import Optional, Dict, Any


class VendHubException(Exception):
    """Базовое исключение для всех ошибок VendHub"""
    
    def __init__(
        self,
        message: str,
        error_code: str = "VENDHUB_ERROR",
        status_code: int = 400,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


# === Исключения аутентификации ===

class AuthException(VendHubException):
    """Базовое исключение для ошибок аутентификации"""
    status_code = 401


class InvalidCredentials(AuthException):
    """Неверные учетные данные"""
    error_code = "INVALID_CREDENTIALS"


class TokenExpired(AuthException):
    """Токен истек"""
    error_code = "TOKEN_EXPIRED"


class TokenInvalid(AuthException):
    """Невалидный токен"""
    error_code = "TOKEN_INVALID"


# === Исключения пользователей ===

class UserException(VendHubException):
    """Базовое исключение для ошибок пользователей"""
    pass


class UserNotFound(UserException):
    """Пользователь не найден"""
    error_code = "USER_NOT_FOUND"
    status_code = 404


class UserAlreadyExists(UserException):
    """Пользователь уже существует"""
    error_code = "USER_ALREADY_EXISTS"
    status_code = 409


class UserNotActive(UserException):
    """Пользователь не активен"""
    error_code = "USER_NOT_ACTIVE"
    status_code = 403


class UserNotVerified(UserException):
    """Пользователь не верифицирован"""
    error_code = "USER_NOT_VERIFIED"
    status_code = 403


# === Исключения доступа ===

class PermissionException(VendHubException):
    """Базовое исключение для ошибок доступа"""
    status_code = 403


class PermissionDenied(PermissionException):
    """Доступ запрещен"""
    error_code = "PERMISSION_DENIED"


class RoleNotFound(PermissionException):
    """Роль не найдена"""
    error_code = "ROLE_NOT_FOUND"
    status_code = 404


# === Исключения машин ===

class MachineException(VendHubException):
    """Базовое исключение для ошибок машин"""
    pass


class MachineNotFound(MachineException):
    """Машина не найдена"""
    error_code = "MACHINE_NOT_FOUND"
    status_code = 404


class MachineAlreadyExists(MachineException):
    """Машина уже существует"""
    error_code = "MACHINE_ALREADY_EXISTS"
    status_code = 409


class MachineNotOperational(MachineException):
    """Машина не работает"""
    error_code = "MACHINE_NOT_OPERATIONAL"


# === Исключения инвентаря ===

class InventoryException(VendHubException):
    """Базовое исключение для ошибок инвентаря"""
    pass


class InsufficientStock(InventoryException):
    """Недостаточно товара на складе"""
    error_code = "INSUFFICIENT_STOCK"


class IngredientNotFound(InventoryException):
    """Ингредиент не найден"""
    error_code = "INGREDIENT_NOT_FOUND"
    status_code = 404


# === Исключения задач ===

class TaskException(VendHubException):
    """Базовое исключение для ошибок задач"""
    pass


class TaskNotFound(TaskException):
    """Задача не найдена"""
    error_code = "TASK_NOT_FOUND"
    status_code = 404


class TaskAlreadyCompleted(TaskException):
    """Задача уже выполнена"""
    error_code = "TASK_ALREADY_COMPLETED"


class TaskNotAssigned(TaskException):
    """Задача не назначена"""
    error_code = "TASK_NOT_ASSIGNED"


# === Исключения финансов ===

class FinanceException(VendHubException):
    """Базовое исключение для финансовых ошибок"""
    pass


class InsufficientFunds(FinanceException):
    """Недостаточно средств"""
    error_code = "INSUFFICIENT_FUNDS"


class TransactionNotFound(FinanceException):
    """Транзакция не найдена"""
    error_code = "TRANSACTION_NOT_FOUND"
    status_code = 404


class InvalidTransactionType(FinanceException):
    """Неверный тип транзакции"""
    error_code = "INVALID_TRANSACTION_TYPE"


# === Исключения инвестиций ===

class InvestmentException(VendHubException):
    """Базовое исключение для ошибок инвестиций"""
    pass


class InvestmentNotFound(InvestmentException):
    """Инвестиция не найдена"""
    error_code = "INVESTMENT_NOT_FOUND"
    status_code = 404


class InvestmentAlreadyExists(InvestmentException):
    """Инвестиция уже существует"""
    error_code = "INVESTMENT_ALREADY_EXISTS"
    status_code = 409


class InvalidSharePercentage(InvestmentException):
    """Неверный процент доли"""
    error_code = "INVALID_SHARE_PERCENTAGE"


# === Исключения валидации ===

class ValidationException(VendHubException):
    """Базовое исключение для ошибок валидации"""
    pass


class InvalidInput(ValidationException):
    """Неверные входные данные"""
    error_code = "INVALID_INPUT"


class MissingRequiredField(ValidationException):
    """Отсутствует обязательное поле"""
    error_code = "MISSING_REQUIRED_FIELD"


# === Исключения интеграций ===

class IntegrationException(VendHubException):
    """Базовое исключение для ошибок интеграций"""
    pass


class ExternalServiceError(IntegrationException):
    """Ошибка внешнего сервиса"""
    error_code = "EXTERNAL_SERVICE_ERROR"
    status_code = 502


class PaymentGatewayError(IntegrationException):
    """Ошибка платежного шлюза"""
    error_code = "PAYMENT_GATEWAY_ERROR"
    status_code = 502