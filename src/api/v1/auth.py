from datetime import timedelta
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status, Form
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.database import get_async_session
from src.db.schemas.user import (
    User, UserCreate, UserLogin, TokenPair, UserTelegramAuth
)
from src.services.auth import AuthService
from src.core.exceptions import (
    InvalidCredentials, UserNotFound, UserAlreadyExists
)
from src.api.dependencies import get_current_user, get_current_active_user

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


@router.post("/register", response_model=User)
async def register(
    user_data: UserCreate,
    session: AsyncSession = Depends(get_async_session)
):
    """
    Регистрация нового пользователя.
    
    - **telegram_id**: ID пользователя в Telegram
    - **phone**: Номер телефона (с +998)
    - **email**: Email адрес
    - **username**: Уникальное имя пользователя
    - **full_name**: Полное имя
    - **password**: Пароль (мин. 8 символов)
    - **role_names**: Список ролей
    """
    auth_service = AuthService(session)
    
    try:
        user = await auth_service.register_user(user_data)
        return user
    except UserAlreadyExists as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/token", response_model=TokenPair)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Вход в систему (OAuth2 совместимый).
    
    Username может быть:
    - Имя пользователя
    - Email
    - Номер телефона
    """
    auth_service = AuthService(session)
    
    try:
        tokens = await auth_service.authenticate_user(
            login=form_data.username,
            password=form_data.password
        )
        return tokens
    except InvalidCredentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверные учетные данные",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/login", response_model=TokenPair)
async def login_custom(
    login_data: UserLogin,
    session: AsyncSession = Depends(get_async_session)
):
    """
    Вход в систему (кастомный endpoint).
    """
    auth_service = AuthService(session)
    
    try:
        tokens = await auth_service.authenticate_user(
            login=login_data.login,
            password=login_data.password
        )
        return tokens
    except InvalidCredentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверные учетные данные"
        )


@router.post("/telegram", response_model=TokenPair)
async def telegram_auth(
    auth_data: UserTelegramAuth,
    session: AsyncSession = Depends(get_async_session)
):
    """
    Авторизация через Telegram.
    """
    auth_service = AuthService(session)
    
    try:
        tokens = await auth_service.authenticate_telegram(auth_data)
        return tokens
    except InvalidCredentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверные данные Telegram"
        )


@router.post("/refresh", response_model=TokenPair)
async def refresh_token(
    refresh_token: str = Form(...),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Обновление токенов.
    """
    auth_service = AuthService(session)
    
    try:
        tokens = await auth_service.refresh_tokens(refresh_token)
        return tokens
    except InvalidCredentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный refresh token"
        )


@router.get("/me", response_model=User)
async def get_me(
    current_user: User = Depends(get_current_active_user)
):
    """
    Получить информацию о текущем пользователе.
    """
    return current_user


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Выход из системы.
    """
    auth_service = AuthService(session)
    await auth_service.logout_user(current_user.id)
    
    return {"message": "Успешный выход"}


@router.post("/verify-email")
async def verify_email(
    token: str,
    session: AsyncSession = Depends(get_async_session)
):
    """
    Подтверждение email.
    """
    auth_service = AuthService(session)
    
    try:
        await auth_service.verify_email(token)
        return {"message": "Email успешно подтвержден"}
    except InvalidCredentials:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный или истекший токен"
        )


@router.post("/reset-password-request")
async def reset_password_request(
    email: str = Form(...),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Запрос на сброс пароля.
    """
    auth_service = AuthService(session)
    
    try:
        await auth_service.request_password_reset(email)
        return {"message": "Инструкции отправлены на email"}
    except UserNotFound:
        # Не раскрываем информацию о существовании пользователя
        return {"message": "Инструкции отправлены на email"}


@router.post("/reset-password")
async def reset_password(
    token: str = Form(...),
    new_password: str = Form(..., min_length=8),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Сброс пароля.
    """
    auth_service = AuthService(session)
    
    try:
        await auth_service.reset_password(token, new_password)
        return {"message": "Пароль успешно изменен"}
    except InvalidCredentials:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный или истекший токен"
        )


@router.get("/permissions")
async def get_my_permissions(
    current_user: User = Depends(get_current_active_user)
):
    """
    Получить права текущего пользователя.
    """
    permissions = set()
    for role in current_user.roles:
        for perm in role.permissions:
            permissions.add(f"{perm.module}:{perm.action}")
    
    return {
        "user_id": current_user.id,
        "roles": [role.name for role in current_user.roles],
        "permissions": sorted(list(permissions))
    }