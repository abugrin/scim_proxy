"""Конфигурация приложения"""

from pydantic_settings import BaseSettings
from pydantic import HttpUrl
from typing import List
import os


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # Upstream API настройки
    upstream_base_url: HttpUrl = "http://localhost:8080/scim/v2" # pyright: ignore[reportAssignmentType]
    upstream_timeout: int = 30
    upstream_max_connections: int = 100
    
    # Прокси настройки
    proxy_host: str = "0.0.0.0"
    proxy_port: int = 8000
    proxy_workers: int = 4
    
    # Кэширование
    cache_ttl: int = 300  # 5 минут
    cache_max_size: int = 1000
    enable_cache: bool = True
    
    # Логирование
    log_level: str = "INFO"
    log_format: str = "json"  # json или text
    
    # Безопасность
    allowed_hosts: str = "*"
    cors_origins: str = "*"
    
    # Производительность
    max_filter_complexity: int = 50  # Максимальная сложность фильтра
    max_response_size: int = 10 * 1024 * 1024  # 10MB
    max_filter_fetch_size: int = 2000  # Максимальное количество записей для загрузки при фильтрации
    filter_fetch_multiplier: int = 20  # Множитель для определения количества загружаемых записей (count * multiplier)
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Глобальный экземпляр настроек
settings = Settings()