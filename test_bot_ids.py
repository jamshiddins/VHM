from typing import List, Optional
from pydantic import Field, validator
from pydantic_settings import BaseSettings

class TestSettings(BaseSettings):
    BOT_ADMIN_IDS: List[int] = Field(default_factory=list)
    
    @validator("BOT_ADMIN_IDS", pre=True)
    def parse_admin_ids(cls, v):
        if isinstance(v, str):
            if not v:
                return []
            return [int(id.strip()) for id in v.split(",") if id.strip()]
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

try:
    settings = TestSettings()
    print(f" BOT_ADMIN_IDS загружены: {settings.BOT_ADMIN_IDS}")
except Exception as e:
    print(f" Ошибка: {e}")
