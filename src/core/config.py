from typing import List, Optional, Union
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
import json
import os


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # API
    API_HOST: str = Field(default="0.0.0.0")
    API_PORT: int = Field(default=8000)
    DEBUG: bool = Field(default=True)
    
    # Project
    PROJECT_NAME: str = Field(default="VendHub")
    PROJECT_VERSION: str = Field(default="1.0.0")
    API_V1_STR: str = Field(default="/api/v1")
    ENVIRONMENT: str = Field(default="development")
    
    # Security
    SECRET_KEY: str = Field(default="your-secret-key-change-in-production")
    JWT_SECRET_KEY: str = Field(default="your-jwt-secret-key-change-in-production")
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)
    
    # Database
    DATABASE_URL: str = Field(default="sqlite+aiosqlite:///./vendhub.db")
    
    # Bot
    BOT_TOKEN: str = Field(default="")
    BOT_WEBHOOK_URL: Optional[str] = Field(default=None)
    BOT_ADMIN_IDS: Union[List[int], str] = Field(default="1,2,3")
    
    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    
    # CORS
    CORS_ORIGINS: Union[List[str], str] = Field(default='["*"]')
    
    @field_validator("BOT_ADMIN_IDS", mode="before")
    @classmethod
    def parse_admin_ids(cls, v):
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        return v
    
    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            if v.startswith("["):
                return json.loads(v)
            else:
                return [x.strip() for x in v.split(",")]
        return v
    
    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, v):
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes", "on")
        return v
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        # Важно: используем validate_assignment для валидации при присваивании
        validate_assignment = True


settings = Settings()