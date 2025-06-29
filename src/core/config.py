from typing import List, Optional, Dict, Any
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator, PostgresDsn
import os
from pathlib import Path


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # Основные настройки
    APP_NAME: str = "VendHub"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = Field("development", env="ENVIRONMENT")
    DEBUG: bool = Field(True, env="DEBUG")
    SECRET_KEY: str = Field(..., env="SECRET_KEY")
    
    # API настройки
    API_PREFIX: str = "/api/v1"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    WORKERS: int = 1
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]
    
    # База данных
    DATABASE_URL: str = Field(..., env="DATABASE_URL")
    
    @validator("DATABASE_URL", pre=True)
    def validate_database_url(cls, v: str) -> str:
        """Преобразование для асинхронного драйвера"""
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://")
        return v
    
    # Redis
    REDIS_URL: str = Field("redis://localhost:6379/0", env="REDIS_URL")
    
    # JWT настройки
    JWT_SECRET_KEY: str = Field(..., env="JWT_SECRET_KEY")
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    
    # Telegram Bot
    BOT_TOKEN: str = Field(..., env="BOT_TOKEN")
    BOT_WEBHOOK_URL: Optional[str] = None
    BOT_ADMIN_IDS: List[int] = []
    USE_WEBHOOK: bool = False
    
    @validator("BOT_ADMIN_IDS", pre=True)
    def parse_admin_ids(cls, v):
        if isinstance(v, str):
            return [int(id.strip()) for id in v.split(",") if id.strip()]
        return v
    
    # Файловое хранилище
    UPLOAD_DIR: Path = Path("./static/uploads")
    MAX_UPLOAD_SIZE_MB: int = 10
    
    # Supabase (опционально)
    SUPABASE_URL: Optional[str] = None
    SUPABASE_KEY: Optional[str] = None
    SUPABASE_BUCKET: str = "vendhub-files"
    
    # Excel настройки
    EXCEL_TEMPLATE_DIR: Path = Path("./static/templates")
    EXCEL_EXPORT_DIR: Path = Path("./static/exports")
    EXCEL_IMPORT_BATCH_SIZE: int = 1000
    
    # Бизнес настройки
    DEFAULT_TIMEZONE: str = "Asia/Tashkent"
    DEFAULT_CURRENCY: str = "UZS"
    VAT_RATE: float = 0.12
    
    # Доли инвестиций
    INVESTOR_SHARE_PERCENT: float = 70.0
    FOUNDER_SHARE_PERCENT: float = 30.0
    
    # Заглушки интеграций
    PAYME_MERCHANT_ID: str = "stub"
    PAYME_SECRET_KEY: str = "stub"
    CLICK_MERCHANT_ID: str = "stub"
    CLICK_SERVICE_ID: str = "stub"
    CLICK_SECRET_KEY: str = "stub"
    UZUM_API_KEY: str = "stub"
    
    # Фискализация
    FISCAL_ENABLED: bool = False
    FISCAL_API_URL: str = "https://api.fiscal.uz"
    FISCAL_TOKEN: str = "stub"
    
    # Карты
    MAPS_PROVIDER: str = "stub"  # google, yandex, osm
    GOOGLE_MAPS_API_KEY: str = "stub"
    YANDEX_MAPS_API_KEY: str = "stub"
    
    # Логирование
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    LOG_FILE: Path = Path("./logs/vendhub.log")
    ENABLE_METRICS: bool = True
    
    # Rate limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000
    
    # Backup
    BACKUP_ENABLED: bool = True
    BACKUP_SCHEDULE: str = "0 3 * * *"  # 3 AM каждый день
    BACKUP_RETENTION_DAYS: int = 30
    
    # Email (заглушка)
    EMAIL_ENABLED: bool = False
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = "VendHub <noreply@vendhub.com>"
    
    # Деплой настройки
    RAILWAY_STATIC_URL: Optional[str] = None
    RENDER_EXTERNAL_URL: Optional[str] = None
    
    # Разработка
    DEV_AUTO_RELOAD: bool = True
    DEV_SEED_DATA: bool = True
    DEV_SHOW_SQL: bool = True
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Создание директорий при инициализации
        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self.EXCEL_TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
        self.EXCEL_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        self.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"
    
    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"
    
    @property
    def database_url_sync(self) -> str:
        """Синхронный URL для Alembic"""
        return self.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    
    def get_cors_origins(self) -> List[str]:
        """Получение разрешенных CORS origins"""
        origins = self.CORS_ORIGINS.copy()
        if self.RAILWAY_STATIC_URL:
            origins.append(self.RAILWAY_STATIC_URL)
        if self.RENDER_EXTERNAL_URL:
            origins.append(self.RENDER_EXTERNAL_URL)
        return origins


# Создание глобального объекта настроек
settings = Settings()
