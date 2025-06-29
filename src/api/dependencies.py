from typing import Optional, Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.database import get_async_session
from src.db.models.user import User
from src.services.auth import AuthService
from src.core.exceptions import TokenInvalid, UserNotActive

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[AsyncSession, Depends(get_async_session)]
) -> User:
    """
    Получение текущего пользователя из токена.
    
    Raises:
        HTTPException: Если токен невалидный или пользователь не найден
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        auth_service = AuthService(session)
        token_data = auth_service.decode_token(token)
        
        user = await auth_service.get_user_by_id(token_data.user_id)
        if user is None:
            raise credentials_exception
            
        return user
        
    except TokenInvalid:
        raise credentials_exception


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """
    Проверка, что пользователь активен.
    
    Raises:
        HTTPException: Если пользователь не активен
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user


async def get_current_verified_user(
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> User:
    """
    Проверка, что пользователь верифицирован.
    
    Raises:
        HTTPException: Если пользователь не верифицирован
    """
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not verified"
        )
    return current_user


class RoleChecker:
    """Проверка ролей пользователя"""
    
    def __init__(self, allowed_roles: list[str]):
        self.allowed_roles = allowed_roles
    
    def __call__(self, user: User = Depends(get_current_active_user)) -> User:
        user_roles = [role.name for role in user.roles]
        if not any(role in user_roles for role in self.allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User doesn't have required role. Required: {self.allowed_roles}"
            )
        return user


class PermissionChecker:
    """Проверка разрешений пользователя"""
    
    def __init__(self, module: str, action: str):
        self.module = module
        self.action = action
    
    def __call__(self, user: User = Depends(get_current_active_user)) -> User:
        if not user.has_permission(self.module, self.action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User doesn't have permission: {self.module}:{self.action}"
            )
        return user


# Алиасы для удобства
RequireRole = RoleChecker
RequirePermission = PermissionChecker

# Предопределенные проверки ролей
require_admin = RoleChecker(["admin"])
require_manager = RoleChecker(["admin", "manager"])
require_operator = RoleChecker(["admin", "manager", "operator"])
require_warehouse = RoleChecker(["admin", "manager", "warehouse"])
require_investor = RoleChecker(["admin", "investor"])


class PaginationParams:
    """Параметры пагинации"""
    
    def __init__(
        self,
        skip: int = 0,
        limit: int = 20,
        max_limit: int = 100
    ):
        self.skip = skip
        self.limit = min(limit, max_limit)


class SortingParams:
    """Параметры сортировки"""
    
    def __init__(
        self,
        sort_by: Optional[str] = None,
        sort_order: str = "asc"
    ):
        self.sort_by = sort_by
        self.sort_order = sort_order.lower()
        
        if self.sort_order not in ["asc", "desc"]:
            self.sort_order = "asc"


class FilterParams:
    """Базовые параметры фильтрации"""
    
    def __init__(
        self,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ):
        self.search = search
        self.is_active = is_active
        self.date_from = date_from
        self.date_to = date_to