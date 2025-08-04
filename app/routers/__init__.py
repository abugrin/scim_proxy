"""Роутеры для SCIM Proxy Service"""

from .users import router as users_router
from .groups import router as groups_router
from .health import router as health_router
from .service_provider_config import router as service_provider_config_router
from .resource_types import router as resource_types_router

__all__ = [
    "users_router",
    "groups_router",
    "health_router",
    "service_provider_config_router",
    "resource_types_router",
]