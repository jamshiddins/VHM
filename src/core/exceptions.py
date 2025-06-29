# Переход в папку проекта
Set-Location "D:\Projects\VHM 1.0"

# Создание файла исключений
$exceptionsContent = @'
from typing import Any, Dict, Optional
from fastapi import HTTPException


class VendHubException(HTTPException):
    """Базовое исключение VendHub"""
    
    def __init__(
        self,
        status_code: int,
        error_code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        super().__init__(status_code=status_code, detail=message)


# Authentication & Authorization
class AuthenticationError(VendHubException):
    """Ошибки аутентификации"""
    
    def __init__(self, message: str = "Не удалось аутентифицировать пользователя"):
        super().__init__(
            status_code=401,
            error_code="AUTHENTICATION_ERROR",
            message=message
        )


class AuthorizationError(VendHubException):
    """Ошибки авторизации"""
    
    def __init__(self, message: str = "Недостаточно прав для выполнения операции"):
        super().__init__(
            status_code=403,
            error_code="AUTHORIZATION_ERROR",
            message=message
        )


class InvalidTokenError(AuthenticationError):
    """Недействительный токен"""
    
    def __init__(self, message: str = "Недействительный или истекший токен"):
        super().__init__(message)
        self.error_code = "INVALID_TOKEN"


class UserNotFoundError(VendHubException):
    """Пользователь не найден"""
    
    def __init__(self, message: str = "Пользователь не найден"):
        super().__init__(
            status_code=404,
            error_code="USER_NOT_FOUND",
            message=message
        )


# Business Logic Errors
class MachineNotFoundError(VendHubException):
    """Автомат не найден"""
    
    def __init__(self, machine_code: str = None):
        message = f"Автомат {machine_code} не найден" if machine_code else "Автомат не найден"
        super().__init__(
            status_code=404,
            error_code="MACHINE_NOT_FOUND",
            message=message
        )


class MachineInactiveError(VendHubException):
    """Автомат неактивен"""
    
    def __init__(self, machine_code: str = None):
        message = f"Автомат {machine_code} неактивен" if machine_code else "Автомат неактивен"
        super().__init__(
            status_code=400,
            error_code="MACHINE_INACTIVE",
            message=message
        )


class InsufficientInventoryError(VendHubException):
    """Недостаточно остатков"""
    
    def __init__(self, ingredient_name: str = None, required: float = None, available: float = None):
        if ingredient_name and required and available:
            message = f"Недостаточно {ingredient_name}: требуется {required}, доступно {available}"
        else:
            message = "Недостаточно остатков для выполнения операции"
        
        super().__init__(
            status_code=400,
            error_code="INSUFFICIENT_INVENTORY",
            message=message,
            details={
                "ingredient": ingredient_name,
                "required": required,
                "available": available
            }
        )


class DuplicateCodeError(VendHubException):
    """Дубликат кода"""
    
    def __init__(self, entity_type: str, code: str):
        super().__init__(
            status_code=400,
            error_code="DUPLICATE_CODE",
            message=f"{entity_type} с кодом {code} уже существует"
        )


# Validation Errors
class ValidationError(VendHubException):
    """Ошибка валидации"""
    
    def __init__(self, message: str, field: str = None):
        super().__init__(
            status_code=422,
            error_code="VALIDATION_ERROR",
            message=message,
            details={"field": field} if field else {}
        )


class InvalidDateRangeError(ValidationError):
    """Неверный диапазон дат"""
    
    def __init__(self, message: str = "Дата начала должна быть меньше даты окончания"):
        super().__init__(message)
        self.error_code = "INVALID_DATE_RANGE"


class InvalidAmountError(ValidationError):
    """Неверная сумма"""
    
    def __init__(self, message: str = "Сумма должна быть положительной"):
        super().__init__(message)
        self.error_code = "INVALID_AMOUNT"


# File & Upload Errors
class FileUploadError(VendHubException):
    """Ошибка загрузки файла"""
    
    def __init__(self, message: str = "Ошибка при загрузке файла"):
        super().__init__(
            status_code=400,
            error_code="FILE_UPLOAD_ERROR",
            message=message
        )


class FileTooLargeError(FileUploadError):
    """Файл слишком большой"""
    
    def __init__(self, max_size_mb: int):
        super().__init__(f"Размер файла превышает {max_size_mb} МБ")
        self.error_code = "FILE_TOO_LARGE"


class UnsupportedFileTypeError(FileUploadError):
    """Неподдерживаемый тип файла"""
    
    def __init__(self, file_type: str, supported_types: list):
        super().__init__(
            f"Неподдерживаемый тип файла: {file_type}. "
            f"Поддерживаемые типы: {', '.join(supported_types)}"
        )
        self.error_code = "UNSUPPORTED_FILE_TYPE"


# Database Errors
class DatabaseError(VendHubException):
    """Ошибка базы данных"""
    
    def __init__(self, message: str = "Ошибка при работе с базой данных"):
        super().__init__(
            status_code=500,
            error_code="DATABASE_ERROR",
            message=message
        )


class RecordNotFoundError(VendHubException):
    """Запись не найдена"""
    
    def __init__(self, entity_type: str = "Запись", entity_id: Any = None):
        message = f"{entity_type} не найдена"
        if entity_id:
            message += f" (ID: {entity_id})"
        
        super().__init__(
            status_code=404,
            error_code="RECORD_NOT_FOUND",
            message=message
        )


class RecordAlreadyExistsError(VendHubException):
    """Запись уже существует"""
    
    def __init__(self, entity_type: str = "Запись"):
        super().__init__(
            status_code=409,
            error_code="RECORD_ALREADY_EXISTS",
            message=f"{entity_type} уже существует"
        )


# External Service Errors
class ExternalServiceError(VendHubException):
    """Ошибка внешнего сервиса"""
    
    def __init__(self, service_name: str, message: str = None):
        default_message = f"Ошибка при обращении к сервису {service_name}"
        super().__init__(
            status_code=502,
            error_code="EXTERNAL_SERVICE_ERROR",
            message=message or default_message
        )


class PaymentServiceError(ExternalServiceError):
    """Ошибка платежного сервиса"""
    
    def __init__(self, service_name: str, message: str = None):
        super().__init__(service_name, message)
        self.error_code = "PAYMENT_SERVICE_ERROR"


class FiscalServiceError(ExternalServiceError):
    """Ошибка фискального сервиса"""
    
    def __init__(self, message: str = "Ошибка фискализации"):
        super().__init__("Fiscal Service", message)
        self.error_code = "FISCAL_SERVICE_ERROR"


# Configuration Errors
class ConfigurationError(VendHubException):
    """Ошибка конфигурации"""
    
    def __init__(self, message: str = "Ошибка конфигурации приложения"):
        super().__init__(
            status_code=500,
            error_code="CONFIGURATION_ERROR",
            message=message
        )


class MissingEnvironmentVariableError(ConfigurationError):
    """Отсутствует переменная окружения"""
    
    def __init__(self, var_name: str):
        super().__init__(f"Отсутствует переменная окружения: {var_name}")
        self.error_code = "MISSING_ENV_VAR"


# Rate Limiting
class RateLimitExceededError(VendHubException):
    """Превышен лимит запросов"""
    
    def __init__(self, message: str = "Превышен лимит запросов"):
        super().__init__(
            status_code=429,
            error_code="RATE_LIMIT_EXCEEDED",
            message=message
        )


# Maintenance
class MaintenanceModeError(VendHubException):
    """Режим технического обслуживания"""
    
    def __init__(self, message: str = "Система находится в режиме технического обслуживания"):
        super().__init__(
            status_code=503,
            error_code="MAINTENANCE_MODE",
            message=message
        )
'@

# Запись в файл
$exceptionsContent | Out-File -FilePath "src\core\exceptions.py" -Encoding UTF8

Write-Host "✅ Файл src\core\exceptions.py создан!" -ForegroundColor Green
Write-Host "📄 Содержит все кастомные исключения для VendHub" -ForegroundColor Yellow
Write-Host "📄 Размер файла: $((Get-Item "src\core\exceptions.py").Length) байт" -ForegroundColor Cyan