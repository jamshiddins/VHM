from typing import List, Optional
from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

class Settings(BaseSettings):
    # Основные настройки
    APP_NAME: str = "VendHub"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = Field("development", env="ENVIRONMENT")
    DEBUG: bool = Field(True, env="DEBUG")
    SECRET_KEY: str = Field(..., env="SECRET_KEY")
    
    # База данных
    DATABASE_URL: str = Field(..., env="DATABASE_URL")
    
    @validator("DATABASE_URL", pre=True)
    def validate_database_url(cls, v: str) -> str:
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://")
        return v
    
    # Redis
    REDIS_URL: str = Field("redis://localhost:6379/0", env="REDIS_URL")
    
    # JWT
    JWT_SECRET_KEY: str = Field(..., env="JWT_SECRET_KEY")
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    
    # Telegram Bot
    BOT_TOKEN: str = Field(..., env="BOT_TOKEN")
    BOT_ADMIN_IDS: List[int] = Field(default_factory=list)
    
    @validator("BOT_ADMIN_IDS", pre=True)
    def parse_admin_ids(cls, v):
        if isinstance(v, str):
            if not v:
                return []
            return [int(id.strip()) for id in v.split(",") if id.strip()]
        return v
    
    # Другие настройки
    LOG_LEVEL: str = "INFO"
    DEV_SHOW_SQL: bool = True
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )
    
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"
    
    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"
    
    @property
    def database_url_sync(self) -> str:
        return self.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

# Создание глобального объекта настроек
settings = Settings()
