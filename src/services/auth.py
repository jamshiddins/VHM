from typing import Optional, List
from datetime import datetime, timedelta
import hashlib
import hmac
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.config import settings
from src.core.exceptions import (
    InvalidCredentials, UserNotFound, UserAlreadyExists,
    UserNotActive
)
from src.db.models.user import User, Role
from src.db.schemas.user import (
    UserCreate, TokenPair, TokenData, UserTelegramAuth
)

# Настройка хеширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """Сервис аутентификации и авторизации"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    # === Хеширование паролей ===
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Проверка пароля"""
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def get_password_hash(password: str) -> str:
        """Хеширование пароля"""
        return pwd_context.hash(password)
    
    # === JWT токены ===
    
    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
        """Создание access токена"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
            )
        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(
            to_encode,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )
        return encoded_jwt
    
    @staticmethod
    def create_refresh_token(data: dict):
        """Создание refresh токена"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(
            days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
        )
        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(
            to_encode,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )
        return encoded_jwt
    
    def create_tokens(self, user: User) -> TokenPair:
        """Создание пары токенов"""
        token_data = {
            "sub": str(user.id),
            "username": user.username,
            "roles": [role.name for role in user.roles]
        }
        
        return TokenPair(
            access_token=self.create_access_token(token_data),
            refresh_token=self.create_refresh_token(token_data)
        )
    
    @staticmethod
    def decode_token(token: str) -> TokenData:
        """Декодирование токена"""
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )
            user_id = int(payload.get("sub"))
            if user_id is None:
                raise InvalidCredentials("Invalid token")
            
            return TokenData(
                user_id=user_id,
                username=payload.get("username"),
                roles=payload.get("roles", [])
            )
        except JWTError:
            raise InvalidCredentials("Invalid token")
    
    # === Работа с пользователями ===
    
    async def get_user_by_login(self, login: str) -> Optional[User]:
        """Получение пользователя по логину (username/email/phone)"""
        # Нормализация телефона
        if login.replace("+", "").isdigit():
            if not login.startswith("+"):
                login = "+" + login
        
        query = select(User).options(selectinload(User.roles)).where(
            or_(
                User.username == login,
                User.email == login,
                User.phone == login
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Получение пользователя по Telegram ID"""
        query = select(User).options(selectinload(User.roles)).where(
            User.telegram_id == telegram_id
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Получение пользователя по ID"""
        query = select(User).options(
            selectinload(User.roles).selectinload(Role.permissions)
        ).where(User.id == user_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    # === Регистрация ===
    
    async def register_user(self, user_data: UserCreate) -> User:
        """Регистрация нового пользователя"""
        # Проверка уникальности
        existing_query = select(User).where(
            or_(
                User.username == user_data.username if user_data.username else False,
                User.email == user_data.email if user_data.email else False,
                User.phone == user_data.phone if user_data.phone else False,
                User.telegram_id == user_data.telegram_id if user_data.telegram_id else False
            )
        )
        existing = await self.session.execute(existing_query)
        if existing.scalar_one_or_none():
            raise UserAlreadyExists("Пользователь с такими данными уже существует")
        
        # Создание пользователя
        user = User(
            telegram_id=user_data.telegram_id,
            phone=user_data.phone,
            email=user_data.email,
            username=user_data.username,
            full_name=user_data.full_name,
            password_hash=self.get_password_hash(user_data.password) if user_data.password else None
        )
        
        # Назначение ролей
        if user_data.role_names:
            roles_query = select(Role).where(Role.name.in_(user_data.role_names))
            roles_result = await self.session.execute(roles_query)
            user.roles = list(roles_result.scalars().all())
        
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        
        return user
    
    # === Аутентификация ===
    
    async def authenticate_user(self, login: str, password: str) -> TokenPair:
        """Аутентификация пользователя"""
        user = await self.get_user_by_login(login)
        
        if not user:
            raise InvalidCredentials("Неверный логин или пароль")
        
        if not user.password_hash:
            raise InvalidCredentials("Пароль не установлен")
        
        if not self.verify_password(password, user.password_hash):
            raise InvalidCredentials("Неверный логин или пароль")
        
        if not user.is_active:
            raise UserNotActive("Пользователь заблокирован")
        
        # Обновление последнего входа
        user.last_login = datetime.utcnow()
        await self.session.commit()
        
        return self.create_tokens(user)
    
    async def authenticate_telegram(self, auth_data: UserTelegramAuth) -> TokenPair:
        """Аутентификация через Telegram"""
        # Проверка подписи
        if not self._verify_telegram_auth(auth_data):
            raise InvalidCredentials("Неверные данные Telegram")
        
        # Поиск или создание пользователя
        user = await self.get_user_by_telegram_id(auth_data.telegram_id)
        
        if not user:
            # Автоматическая регистрация
            full_name = f"{auth_data.first_name or ''} {auth_data.last_name or ''}".strip()
            user_data = UserCreate(
                telegram_id=auth_data.telegram_id,
                username=auth_data.username,
                full_name=full_name or f"User {auth_data.telegram_id}",
                role_names=["operator"]  # По умолчанию оператор
            )
            user = await self.register_user(user_data)
        
        if not user.is_active:
            raise UserNotActive("Пользователь заблокирован")
        
        # Обновление последнего входа
        user.last_login = datetime.utcnow()
        await self.session.commit()
        
        return self.create_tokens(user)
    
    def _verify_telegram_auth(self, auth_data: UserTelegramAuth) -> bool:
        """Проверка подписи Telegram"""
        check_hash = auth_data.hash
        auth_dict = auth_data.dict()
        del auth_dict['hash']
        
        # Сортировка и формирование строки
        data_check_arr = []
        for key in sorted(auth_dict.keys()):
            if auth_dict[key] is not None:
                data_check_arr.append(f"{key}={auth_dict[key]}")
        
        data_check_string = "\n".join(data_check_arr)
        
        # Проверка подписи
        secret_key = hashlib.sha256(settings.BOT_TOKEN.encode()).digest()
        h = hmac.new(
            secret_key,
            msg=data_check_string.encode(),
            digestmod=hashlib.sha256
        )
        
        return h.hexdigest() == check_hash
    
    # === Обновление токенов ===
    
    async def refresh_tokens(self, refresh_token: str) -> TokenPair:
        """Обновление токенов"""
        try:
            payload = jwt.decode(
                refresh_token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )
            
            if payload.get("type") != "refresh":
                raise InvalidCredentials("Invalid token type")
            
            user_id = int(payload.get("sub"))
            user = await self.get_user_by_id(user_id)
            
            if not user:
                raise UserNotFound("User not found")
            
            if not user.is_active:
                raise UserNotActive("User is not active")
            
            return self.create_tokens(user)
            
        except JWTError:
            raise InvalidCredentials("Invalid refresh token")
    
    # === Дополнительные методы ===
    
    async def logout_user(self, user_id: int):
        """Выход пользователя (можно добавить blacklist токенов)"""
        # TODO: Реализовать blacklist токенов в Redis
        pass
    
    async def verify_email(self, token: str):
        """Подтверждение email"""
        # TODO: Реализовать подтверждение email
        pass
    
    async def request_password_reset(self, email: str):
        """Запрос сброса пароля"""
        # TODO: Реализовать отправку email
        pass
    
    async def reset_password(self, token: str, new_password: str):
        """Сброс пароля"""
        # TODO: Реализовать сброс пароля
        pass