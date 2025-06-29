from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, validator
from uuid import UUID


class RoleBase(BaseModel):
    """Базовая схема роли"""
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None


class RoleCreate(RoleBase):
    """Схема для создания роли"""
    pass


class RoleUpdate(BaseModel):
    """Схема для обновления роли"""
    display_name: Optional[str] = None
    description: Optional[str] = None


class Role(RoleBase):
    """Схема роли для чтения"""
    id: int
    is_system: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserBase(BaseModel):
    """Базовая схема пользователя"""
    telegram_id: Optional[int] = None
    phone: Optional[str] = Field(None, regex=r'^\+?[1-9]\d{1,14}$')
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=3, max_length=100)
    full_name: str = Field(..., min_length=2, max_length=255)
    
    @validator('phone')
    def validate_phone(cls, v):
        if v and not v.startswith('+'):
            v = '+' + v
        return v


class UserCreate(UserBase):
    """Схема для создания пользователя"""
    password: Optional[str] = Field(None, min_length=8)
    role_names: List[str] = Field(default_factory=list)
    
    @validator('password')
    def validate_password(cls, v):
        if v:
            if not any(c.isupper() for c in v):
                raise ValueError('Пароль должен содержать заглавные буквы')
            if not any(c.islower() for c in v):
                raise ValueError('Пароль должен содержать строчные буквы')
            if not any(c.isdigit() for c in v):
                raise ValueError('Пароль должен содержать цифры')
        return v


class UserUpdate(BaseModel):
    """Схема для обновления пользователя"""
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    settings: Optional[Dict[str, Any]] = None


class UserPasswordUpdate(BaseModel):
    """Схема для изменения пароля"""
    current_password: str
    new_password: str = Field(..., min_length=8)
    
    @validator('new_password')
    def validate_password(cls, v, values):
        if v == values.get('current_password'):
            raise ValueError('Новый пароль не должен совпадать с текущим')
        return v


class User(UserBase):
    """Схема пользователя для чтения"""
    id: int
    uuid: UUID
    is_active: bool
    is_verified: bool
    last_login: Optional[datetime]
    settings: Dict[str, Any]
    roles: List[Role]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserWithStats(User):
    """Пользователь со статистикой"""
    managed_machines_count: int = 0
    active_tasks_count: int = 0
    completed_tasks_count: int = 0
    total_investment: float = 0


class UserLogin(BaseModel):
    """Схема для входа"""
    login: str  # username, email или phone
    password: str


class TokenPair(BaseModel):
    """Пара токенов"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Данные из токена"""
    user_id: int
    username: Optional[str] = None
    roles: List[str] = Field(default_factory=list)


class UserTelegramAuth(BaseModel):
    """Авторизация через Telegram"""
    telegram_id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    auth_date: int
    hash: str


class UserFilter(BaseModel):
    """Фильтры для списка пользователей"""
    search: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    has_telegram: Optional[bool] = None
    created_from: Optional[datetime] = None
    created_to: Optional[datetime] = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
