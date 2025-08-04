"""Кастомные исключения для SCIM Proxy Service"""


class SCIMProxyError(Exception):
    """Базовое исключение для SCIM Proxy Service"""
    
    def __init__(self, message: str, status_code: int = 500, scim_type: str | None = None):
        self.message = message
        self.status_code = status_code
        self.scim_type = scim_type
        super().__init__(message)


class InvalidFilterError(SCIMProxyError):
    """Ошибка при парсинге или валидации фильтра"""
    
    def __init__(self, message: str):
        super().__init__(
            message=message,
            status_code=400,
            scim_type="invalidFilter"
        )


class FilterEvaluationError(SCIMProxyError):
    """Ошибка при применении фильтра к данным"""
    
    def __init__(self, message: str):
        super().__init__(
            message=message,
            status_code=500,
            scim_type="filterEvaluation"
        )


class UpstreamError(SCIMProxyError):
    """Ошибка при обращении к upstream API"""
    
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(
            message=message,
            status_code=status_code,
            scim_type="upstream"
        )


class ConfigurationError(SCIMProxyError):
    """Ошибка конфигурации"""
    
    def __init__(self, message: str):
        super().__init__(
            message=message,
            status_code=500,
            scim_type="configuration"
        )


class PatchOperationError(SCIMProxyError):
    """Ошибка при выполнении PATCH операции"""
    
    def __init__(self, message: str):
        super().__init__(
            message=message,
            status_code=400,
            scim_type="invalidPatch"
        )


class ResourceNotFoundError(SCIMProxyError):
    """Ресурс не найден"""
    
    def __init__(self, resource_id: str):
        super().__init__(
            message=f"Resource {resource_id} not found",
            status_code=404,
            scim_type="resourceNotFound"
        )


class TooManyRequestsError(SCIMProxyError):
    """Слишком много запросов"""
    
    def __init__(self, message: str = "Too many requests"):
        super().__init__(
            message=message,
            status_code=429,
            scim_type="tooManyRequests"
        )