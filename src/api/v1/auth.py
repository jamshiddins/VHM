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
    Р РµРіРёСЃС‚СЂР°С†РёСЏ РЅРѕРІРѕРіРѕ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ.
    
    - **telegram_id**: ID РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ РІ Telegram
    - **phone**: РќРѕРјРµСЂ С‚РµР»РµС„РѕРЅР° (СЃ +998)
    - **email**: Email Р°РґСЂРµСЃ
    - **username**: РЈРЅРёРєР°Р»СЊРЅРѕРµ РёРјСЏ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ
    - **full_name**: РџРѕР»РЅРѕРµ РёРјСЏ
    - **password**: РџР°СЂРѕР»СЊ (РјРёРЅ. 8 СЃРёРјРІРѕР»РѕРІ)
    - **role_names**: РЎРїРёСЃРѕРє СЂРѕР»РµР№
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
    Р’С…РѕРґ РІ СЃРёСЃС‚РµРјСѓ (OAuth2 СЃРѕРІРјРµСЃС‚РёРјС‹Р№).
    
    Username РјРѕР¶РµС‚ Р±С‹С‚СЊ:
    - РРјСЏ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ
    - Email
    - РќРѕРјРµСЂ С‚РµР»РµС„РѕРЅР°
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
            detail="РќРµРІРµСЂРЅС‹Рµ СѓС‡РµС‚РЅС‹Рµ РґР°РЅРЅС‹Рµ",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/login", response_model=TokenPair)
async def login_custom(
    login_data: UserLogin,
    session: AsyncSession = Depends(get_async_session)
):
    """
    Р’С…РѕРґ РІ СЃРёСЃС‚РµРјСѓ (РєР°СЃС‚РѕРјРЅС‹Р№ endpoint).
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
            detail="РќРµРІРµСЂРЅС‹Рµ СѓС‡РµС‚РЅС‹Рµ РґР°РЅРЅС‹Рµ"
        )


@router.post("/telegram", response_model=TokenPair)
async def telegram_auth(
    auth_data: UserTelegramAuth,
    session: AsyncSession = Depends(get_async_session)
):
    """
    РђРІС‚РѕСЂРёР·Р°С†РёСЏ С‡РµСЂРµР· Telegram.
    """
    auth_service = AuthService(session)
    
    try:
        tokens = await auth_service.authenticate_telegram(auth_data)
        return tokens
    except InvalidCredentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="РќРµРІРµСЂРЅС‹Рµ РґР°РЅРЅС‹Рµ Telegram"
        )


@router.post("/refresh", response_model=TokenPair)
async def refresh_token(
    refresh_token: str = Form(...),
    session: AsyncSession = Depends(get_async_session)
):
    """
    РћР±РЅРѕРІР»РµРЅРёРµ С‚РѕРєРµРЅРѕРІ.
    """
    auth_service = AuthService(session)
    
    try:
        tokens = await auth_service.refresh_tokens(refresh_token)
        return tokens
    except InvalidCredentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="РќРµРІР°Р»РёРґРЅС‹Р№ refresh token"
        )


@router.get("/me", response_model=User)
async def get_me(
    current_user: User = Depends(get_current_active_user)
):
    """
    РџРѕР»СѓС‡РёС‚СЊ РёРЅС„РѕСЂРјР°С†РёСЋ Рѕ С‚РµРєСѓС‰РµРј РїРѕР»СЊР·РѕРІР°С‚РµР»Рµ.
    """
    return current_user


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Р’С‹С…РѕРґ РёР· СЃРёСЃС‚РµРјС‹.
    """
    auth_service = AuthService(session)
    await auth_service.logout_user(current_user.id)
    
    return {"message": "РЈСЃРїРµС€РЅС‹Р№ РІС‹С…РѕРґ"}


@router.post("/verify-email")
async def verify_email(
    token: str,
    session: AsyncSession = Depends(get_async_session)
):
    """
    РџРѕРґС‚РІРµСЂР¶РґРµРЅРёРµ email.
    """
    auth_service = AuthService(session)
    
    try:
        await auth_service.verify_email(token)
        return {"message": "Email СѓСЃРїРµС€РЅРѕ РїРѕРґС‚РІРµСЂР¶РґРµРЅ"}
    except InvalidCredentials:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="РќРµРІРµСЂРЅС‹Р№ РёР»Рё РёСЃС‚РµРєС€РёР№ С‚РѕРєРµРЅ"
        )


@router.post("/reset-password-request")
async def reset_password_request(
    email: str = Form(...),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Р—Р°РїСЂРѕСЃ РЅР° СЃР±СЂРѕСЃ РїР°СЂРѕР»СЏ.
    """
    auth_service = AuthService(session)
    
    try:
        await auth_service.request_password_reset(email)
        return {"message": "РРЅСЃС‚СЂСѓРєС†РёРё РѕС‚РїСЂР°РІР»РµРЅС‹ РЅР° email"}
    except UserNotFound:
        # РќРµ СЂР°СЃРєСЂС‹РІР°РµРј РёРЅС„РѕСЂРјР°С†РёСЋ Рѕ СЃСѓС‰РµСЃС‚РІРѕРІР°РЅРёРё РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ
        return {"message": "РРЅСЃС‚СЂСѓРєС†РёРё РѕС‚РїСЂР°РІР»РµРЅС‹ РЅР° email"}


@router.post("/reset-password")
async def reset_password(
    token: str = Form(...),
    new_password: str = Form(..., min_length=8),
    session: AsyncSession = Depends(get_async_session)
):
    """
    РЎР±СЂРѕСЃ РїР°СЂРѕР»СЏ.
    """
    auth_service = AuthService(session)
    
    try:
        await auth_service.reset_password(token, new_password)
        return {"message": "РџР°СЂРѕР»СЊ СѓСЃРїРµС€РЅРѕ РёР·РјРµРЅРµРЅ"}
    except InvalidCredentials:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="РќРµРІРµСЂРЅС‹Р№ РёР»Рё РёСЃС‚РµРєС€РёР№ С‚РѕРєРµРЅ"
        )


@router.get("/permissions")
async def get_my_permissions(
    current_user: User = Depends(get_current_active_user)
):
    """
    РџРѕР»СѓС‡РёС‚СЊ РїСЂР°РІР° С‚РµРєСѓС‰РµРіРѕ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ.
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
