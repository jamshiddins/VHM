from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import time
import logging
from src.core.config import settings
from src.db.database import init_db, close_db
from src.api.v1 import auth, machines, inventory, finance, routes, recipes, investors, reports
from src.core.exceptions import VendHubException
from src.utils.logger import setup_logging

# Настройка логирования
logger = setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    
    # Инициализация БД
    if settings.is_development and settings.DEV_AUTO_RELOAD:
        await init_db()
        logger.info("Database initialized")
    
    # TODO: Запуск фоновых задач (планировщик, очистка и т.д.)
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    await close_db()
    logger.info("Database connections closed")


# Создание приложения
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Система управления вендинговой сетью",
    docs_url=f"{settings.API_PREFIX}/docs" if settings.DEBUG else None,
    redoc_url=f"{settings.API_PREFIX}/redoc" if settings.DEBUG else None,
    openapi_url=f"{settings.API_PREFIX}/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if settings.is_production:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*.railway.app", "*.onrender.com", "localhost"]
    )


# Middleware для логирования времени запросов
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    logger.info(
        f"{request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Time: {process_time:.3f}s"
    )
    
    response.headers["X-Process-Time"] = str(process_time)
    return response


# Обработчик ошибок
@app.exception_handler(VendHubException)
async def vendhub_exception_handler(request: Request, exc: VendHubException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_code,
            "message": exc.message,
            "details": exc.details
        }
    )


# Health check
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT
    }


# API routes
app.include_router(auth.router, prefix=f"{settings.API_PREFIX}/auth", tags=["Аутентификация"])
app.include_router(machines.router, prefix=f"{settings.API_PREFIX}/machines", tags=["Автоматы"])
app.include_router(inventory.router, prefix=f"{settings.API_PREFIX}/inventory", tags=["Остатки"])
app.include_router(finance.router, prefix=f"{settings.API_PREFIX}/finance", tags=["Финансы"])
app.include_router(routes.router, prefix=f"{settings.API_PREFIX}/routes", tags=["Маршруты"])
app.include_router(recipes.router, prefix=f"{settings.API_PREFIX}/recipes", tags=["Рецепты"])
app.include_router(investors.router, prefix=f"{settings.API_PREFIX}/investors", tags=["Инвесторы"])
app.include_router(reports.router, prefix=f"{settings.API_PREFIX}/reports", tags=["Отчеты"])


# Root endpoint
@app.get("/")
async def root():
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "docs": f"{settings.API_PREFIX}/docs" if settings.DEBUG else None
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.is_development and settings.DEV_AUTO_RELOAD,
        workers=settings.WORKERS if settings.is_production else 1,
        log_level=settings.LOG_LEVEL.lower()
    )
