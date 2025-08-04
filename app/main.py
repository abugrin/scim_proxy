"""Основное FastAPI приложение для SCIM Proxy Service"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import sys
import time
from contextlib import asynccontextmanager

from .config import settings
from .routers import users_router, groups_router, health_router, service_provider_config_router, resource_types_router
from .services.proxy import proxy_service
from .utils.exceptions import SCIMProxyError
from .models.scim import SCIMError


# Настройка логирования
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    # Startup
    logger.info("Starting SCIM Proxy Service...")
    logger.info(f"Upstream URL: {settings.upstream_base_url}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down SCIM Proxy Service...")
    await proxy_service.close()


# Создание FastAPI приложения
app = FastAPI(
    title="SCIM Proxy Service",
    description="Высокопроизводительный прокси для модернизации SCIM API с поддержкой фильтров",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Настройка CORS
cors_origins = settings.cors_origins.split(",") if settings.cors_origins != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Обработчик исключений SCIM Proxy
@app.exception_handler(SCIMProxyError)
async def scim_proxy_exception_handler(request: Request, exc: SCIMProxyError):
    """Обработчик кастомных исключений SCIM Proxy"""
    logger.error(f"SCIM Proxy Error: {exc.message}")
    
    error_response = SCIMError(
        status=exc.status_code,
        scimType=exc.scim_type,
        detail=exc.message
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.dict()
    )


# Обработчик общих HTTP исключений
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Обработчик HTTP исключений"""
    logger.error(f"HTTP Error: {exc.detail}")
    
    error_response = SCIMError(
        status=exc.status_code,
        detail=str(exc.detail)
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.dict()
    )


# Обработчик неожиданных исключений
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Обработчик неожиданных исключений"""
    logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
    
    error_response = SCIMError(
        status=500,
        detail="Internal server error"
    )
    
    return JSONResponse(
        status_code=500,
        content=error_response.dict()
    )


# Middleware для логирования запросов
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware для логирования HTTP запросов"""
    start_time = time.time()
    
    # Логируем входящий запрос
    logger.info(f"Request: {request.method} {request.url}")
    
    response = await call_next(request)
    
    # Логируем время выполнения
    process_time = time.time() - start_time
    logger.info(f"Response: {response.status_code} - {process_time:.3f}s")
    
    return response


# Подключение роутеров
app.include_router(health_router)

# Подключаем роутеры с различными префиксами для максимальной совместимости:
# 1. Основной SCIM v2 путь (без /scim префикса)
app.include_router(users_router, prefix="/v2")
app.include_router(groups_router, prefix="/v2")
app.include_router(service_provider_config_router, prefix="/v2")
app.include_router(resource_types_router, prefix="/v2")

# 2. Без префикса для обратной совместимости
app.include_router(users_router)
app.include_router(groups_router)
app.include_router(service_provider_config_router)
app.include_router(resource_types_router)


if __name__ == "__main__":
    import uvicorn
    import time
    
    uvicorn.run(
        "app.main:app",
        host=settings.proxy_host,
        port=settings.proxy_port,
        reload=True,
        log_level=settings.log_level.lower()
    )