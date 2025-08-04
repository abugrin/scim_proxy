"""Users роутер для SCIM API"""

from fastapi import APIRouter, Query, HTTPException, Request, Depends
from typing import Optional, List, Dict, Any
import logging

from ..models.scim import User, ListResponse, PatchRequest, SCIMError
from ..services.proxy import proxy_service
from ..services.filter_parser import FilterParser
from ..services.filter_engine import FilterEngine
from ..utils.exceptions import (
    InvalidFilterError, 
    FilterEvaluationError, 
    UpstreamError,
    ResourceNotFoundError
)

router = APIRouter(prefix="/Users", tags=["users"])
logger = logging.getLogger(__name__)

# Инициализируем сервисы
filter_parser = FilterParser()
filter_engine = FilterEngine()


def get_request_headers(request: Request) -> Dict[str, str]:
    """Извлекает заголовки из запроса"""
    return dict(request.headers)


@router.get("", response_model=ListResponse)
async def list_users(
    request: Request,
    filter: Optional[str] = Query(None, description="SCIM filter expression"),
    attributes: Optional[str] = Query(None, description="Comma-separated list of attributes to return"),
    excluded_attributes: Optional[str] = Query(None, alias="excludedAttributes", description="Comma-separated list of attributes to exclude"),
    sort_by: Optional[str] = Query(None, alias="sortBy", description="Attribute to sort by"),
    sort_order: Optional[str] = Query("ascending", alias="sortOrder", description="Sort order: ascending or descending"),
    start_index: int = Query(1, alias="startIndex", ge=1, description="1-based index of the first result"),
    count: int = Query(100, ge=1, le=1000, description="Number of results per page")
) -> ListResponse:
    """Получение списка пользователей с поддержкой фильтрации"""
    
    try:
        logger.info(f"Processing request with filter: {filter}")
        headers = get_request_headers(request)
        logger.info(f"Headers extracted: {len(headers)} headers")
        
        # Парсим атрибуты если указаны
        attributes_list = attributes.split(",") if attributes else None
        excluded_attributes_list = excluded_attributes.split(",") if excluded_attributes else None
        logger.info(f"Attributes parsed - attributes: {attributes_list}, excluded: {excluded_attributes_list}")
        
        # Если есть фильтр, используем специальную логику для загрузки всех данных
        if filter:
            try:
                logger.info(f"Parsing filter: {filter}")
                # Парсим фильтр
                filter_expr = filter_parser.parse(filter)
                logger.info(f"Filter parsed successfully: {filter_expr}")
                
                # Загружаем больше данных для фильтрации
                from ..config import settings
                max_fetch = min(count * settings.filter_fetch_multiplier, settings.max_filter_fetch_size)
                logger.info(f"Loading up to {max_fetch} users for filtering")
                
                all_users = await proxy_service.get_all_users_for_filtering(
                    headers=headers,
                    max_results=max_fetch,
                    attributes=attributes_list,
                    excluded_attributes=excluded_attributes_list
                )
                logger.info(f"Loaded {len(all_users)} users for filtering")
                
                # Применяем фильтр ко всем загруженным данным
                logger.info(f"Applying filter to {len(all_users)} users")
                filtered_users = filter_engine.apply_filter(all_users, filter_expr)
                logger.info(f"Filter applied, {len(filtered_users)} users match")
                
                # Применяем пагинацию к отфильтрованным результатам
                start_idx = start_index - 1  # Преобразуем в 0-based индекс
                end_idx = start_idx + count
                paginated_users = filtered_users[start_idx:end_idx]
                
                # Создаем ответ
                response = ListResponse(
                    schemas=["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
                    totalResults=len(filtered_users),
                    startIndex=start_index,
                    itemsPerPage=len(paginated_users),
                    Resources=paginated_users
                )
                
                logger.info(f"Returning {len(paginated_users)} users (page {start_index}-{start_index + len(paginated_users) - 1} of {len(filtered_users)} total)")
                
            except InvalidFilterError as e:
                logger.error(f"Invalid filter error: {e}", exc_info=True)
                raise HTTPException(status_code=400, detail=str(e))
            except FilterEvaluationError as e:
                logger.error(f"Filter evaluation error: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail="Filter evaluation failed")
            except Exception as e:
                logger.error(f"Unexpected filter error: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"Filter processing failed: {str(e)}")
        
        else:
            # Без фильтра используем обычную пагинацию
            logger.info(f"No filter, using standard pagination with start_index={start_index}, count={count}")
            response = await proxy_service.get_users(
                headers=headers,
                start_index=start_index,
                count=count,
                attributes=attributes_list,
                excluded_attributes=excluded_attributes_list
            )
            logger.info(f"Upstream API returned {len(response.Resources)} users")
        
        return response
        
    except UpstreamError as e:
        logger.error(f"Upstream error: {e}", exc_info=True)
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Unexpected error in list_users: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{user_id}", response_model=User)
async def get_user(
    user_id: str,
    request: Request
) -> User:
    """Получение пользователя по ID"""
    
    try:
        headers = get_request_headers(request)
        user = await proxy_service.get_user(user_id, headers)
        return user
        
    except UpstreamError as e:
        logger.error(f"Upstream error: {e}")
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Unexpected error in get_user: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=User, status_code=201)
async def create_user(
    user_data: Dict[str, Any],
    request: Request
) -> User:
    """Создание нового пользователя"""
    
    try:
        headers = get_request_headers(request)
        user = await proxy_service.create_user(user_data, headers)
        return user
        
    except UpstreamError as e:
        logger.error(f"Upstream error: {e}")
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Unexpected error in create_user: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{user_id}", response_model=User)
async def update_user(
    user_id: str,
    user_data: Dict[str, Any],
    request: Request
) -> User:
    """Полное обновление пользователя"""
    
    try:
        headers = get_request_headers(request)
        user = await proxy_service.update_user(user_id, user_data, headers)
        return user
        
    except UpstreamError as e:
        logger.error(f"Upstream error: {e}")
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Unexpected error in update_user: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{user_id}", response_model=User)
async def patch_user(
    user_id: str,
    patch_request: PatchRequest,
    request: Request
) -> User:
    """Частичное обновление пользователя через PATCH операции"""
    
    try:
        headers = get_request_headers(request)
        
        # Преобразуем PatchRequest в dict для отправки upstream
        patch_data = patch_request.dict()
        
        user = await proxy_service.patch_user(user_id, patch_data, headers)
        return user
        
    except UpstreamError as e:
        logger.error(f"Upstream error: {e}")
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Unexpected error in patch_user: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: str,
    request: Request
):
    """Удаление пользователя"""
    
    try:
        headers = get_request_headers(request)
        await proxy_service.delete_user(user_id, headers)
        return None
        
    except UpstreamError as e:
        logger.error(f"Upstream error: {e}")
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Unexpected error in delete_user: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")