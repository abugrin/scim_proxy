"""Users роутер для SCIM API"""

from fastapi import APIRouter, Query, HTTPException, Request, Depends
from typing import Optional, List, Dict, Any, Union
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


def _filter_user_attributes(user: Union[User, Dict[str, Any]], attributes: Optional[List[str]] = None, excluded_attributes: Optional[List[str]] = None) -> Union[User, Dict[str, Any]]:
    """Фильтрует атрибуты пользователя согласно SCIM спецификации"""
    
    # Если фильтрация не нужна, возвращаем как есть
    if not attributes and not excluded_attributes:
        return user
    
    # Преобразуем пользователя в словарь
    if isinstance(user, dict):
        user_dict = user.copy()
    elif hasattr(user, 'dict') and callable(getattr(user, 'dict')):
        user_dict = user.dict(by_alias=True, exclude_none=False)
    else:
        user_dict = user.__dict__.copy()
    
    # Если указаны конкретные атрибуты для включения
    if attributes:
        # Всегда включаем обязательные атрибуты SCIM
        required_attributes = {'id', 'schemas'}
        attributes_set = set(attributes) | required_attributes
        
        # Фильтруем только указанные атрибуты
        filtered_dict = {}
        for attr in attributes_set:
            if attr in user_dict:
                filtered_dict[attr] = user_dict[attr]
        
        return filtered_dict
    
    # Если указаны атрибуты для исключения
    if excluded_attributes:
        # Никогда не исключаем обязательные атрибуты SCIM
        required_attributes = {'id', 'schemas'}
        excluded_set = set(excluded_attributes) - required_attributes
        
        # Исключаем указанные атрибуты
        filtered_dict = user_dict.copy()
        for attr in excluded_set:
            filtered_dict.pop(attr, None)
        
        return filtered_dict
    
    # Если фильтрация не указана, возвращаем все атрибуты
    return user_dict


def _apply_attribute_filtering(users: List[Union[User, Dict[str, Any]]], attributes: Optional[List[str]] = None, excluded_attributes: Optional[List[str]] = None) -> List[Union[User, Dict[str, Any]]]:
    """Применяет фильтрацию атрибутов к списку пользователей"""
    if not attributes and not excluded_attributes:
        # Если фильтрация не нужна, возвращаем как есть
        return users
    
    filtered_users = []
    for user in users:
        filtered_user = _filter_user_attributes(user, attributes, excluded_attributes)
        filtered_users.append(filtered_user)
    
    return filtered_users


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
                
                # Применяем фильтрацию атрибутов к отфильтрованным результатам
                filtered_paginated_users = _apply_attribute_filtering(list(paginated_users), attributes_list, excluded_attributes_list)
                
                # Создаем ответ
                response = ListResponse(
                    schemas=["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
                    totalResults=len(filtered_users),
                    startIndex=start_index,
                    itemsPerPage=len(filtered_paginated_users),
                    Resources=filtered_paginated_users
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
                attributes=None,  # НЕ передаем в upstream API
                excluded_attributes=None  # НЕ передаем в upstream API
            )
            logger.info(f"Upstream API returned {len(response.Resources)} users")
            
            # Применяем фильтрацию атрибутов на уровне прокси
            if attributes_list or excluded_attributes_list:
                logger.info(f"Applying attribute filtering: attributes={attributes_list}, excluded={excluded_attributes_list}")
                filtered_resources = _apply_attribute_filtering(response.Resources, attributes_list, excluded_attributes_list)
                
                # Создаем новый ответ с отфильтрованными атрибутами
                response = ListResponse(
                    schemas=response.schemas,
                    totalResults=response.totalResults,
                    startIndex=response.startIndex,
                    itemsPerPage=response.itemsPerPage,
                    Resources=filtered_resources
                )
                logger.info(f"Attribute filtering applied to {len(filtered_resources)} users")
        
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


async def _adapt_patch_for_upstream(
    patch_request: PatchRequest,
    user_id: str,
    headers: Dict[str, str]
) -> Dict[str, Any]:
    """Адаптирует PATCH запрос под требования upstream API"""
    adapted_operations = []
    add_operations_to_convert = []
    
    # Сначала собираем операции add с фильтрацией, которые нужно преобразовать
    for op in patch_request.Operations:
        if op.op.lower() == "add" and op.path and "[" in op.path and "]" in op.path:
            add_operations_to_convert.append(op)
        else:
            # Обычные операции добавляем как есть
            adapted_op: Dict[str, Any] = {
                "op": op.op.lower()  # Приводим операцию к нижнему регистру для upstream API
            }
            
            # Добавляем path если указан
            if op.path is not None:
                adapted_op["path"] = op.path
            
            # Добавляем value если указано, с правильной типизацией
            if op.value is not None:
                # Специальная обработка для булевых значений
                if isinstance(op.value, bool):
                    adapted_op["value"] = op.value
                elif isinstance(op.value, str) and op.value.lower() in ['true', 'false']:
                    adapted_op["value"] = op.value.lower() == 'true'
                else:
                    adapted_op["value"] = op.value
            
            adapted_operations.append(adapted_op)
    
    # Если есть операции add с фильтрацией, преобразуем их
    if add_operations_to_convert:
        logger.info(f"Converting {len(add_operations_to_convert)} add operations with filtering to replace operations")
        
        try:
            # Получаем текущие данные пользователя
            current_user = await proxy_service.get_user(user_id, headers)
            current_user_dict = current_user.dict() if hasattr(current_user, 'dict') else current_user.__dict__
            
            # Группируем операции по базовому пути (например, phoneNumbers)
            operations_by_path = {}
            for op in add_operations_to_convert:
                # Извлекаем базовый путь (например, "phoneNumbers" из "phoneNumbers[type eq \"work\"].value")
                base_path = op.path.split('[')[0]
                if base_path not in operations_by_path:
                    operations_by_path[base_path] = []
                operations_by_path[base_path].append(op)
            
            # Обрабатываем каждый базовый путь
            for base_path, ops in operations_by_path.items():
                logger.info(f"Processing {len(ops)} add operations for path: {base_path}")
                
                # Получаем текущий массив
                current_array = current_user_dict.get(base_path, [])
                if not isinstance(current_array, list):
                    current_array = []
                
                # Применяем операции add
                updated_array = current_array.copy()
                
                for op in ops:
                    # Парсим фильтр из path (например, "type eq \"work\"")
                    if '[' in op.path and ']' in op.path:
                        filter_part = op.path.split('[')[1].split(']')[0]
                        field_part = op.path.split('].')[1] if '].' in op.path else None
                        
                        # Простой парсинг фильтра "type eq \"work\""
                        if ' eq ' in filter_part:
                            filter_field, filter_value = filter_part.split(' eq ')
                            filter_field = filter_field.strip()
                            filter_value = filter_value.strip().strip('"\'')
                            
                            # Ищем существующий элемент с таким фильтром
                            existing_item = None
                            for item in updated_array:
                                if isinstance(item, dict) and item.get(filter_field) == filter_value:
                                    existing_item = item
                                    break
                            
                            if existing_item:
                                # Обновляем существующий элемент
                                if field_part:
                                    existing_item[field_part] = op.value
                                else:
                                    # Если нет field_part, заменяем весь объект
                                    if isinstance(op.value, dict):
                                        existing_item.update(op.value)
                                logger.info(f"Updated existing item with {filter_field}={filter_value}")
                            else:
                                # Создаем новый элемент
                                new_item = {filter_field: filter_value}
                                if field_part:
                                    new_item[field_part] = op.value
                                elif isinstance(op.value, dict):
                                    new_item.update(op.value)
                                else:
                                    new_item['value'] = op.value
                                
                                updated_array.append(new_item)
                                logger.info(f"Added new item with {filter_field}={filter_value}")
                
                # Создаем операцию replace для всего массива
                replace_op = {
                    "op": "replace",
                    "path": base_path,
                    "value": updated_array
                }
                adapted_operations.append(replace_op)
                logger.info(f"Created replace operation for {base_path} with {len(updated_array)} items")
                
        except Exception as e:
            logger.error(f"Failed to convert add operations: {e}")
            # В случае ошибки, пропускаем операции add с предупреждением
            logger.warning("Falling back to skipping add operations with filtering")
    
    # Исправляем схему если есть опечатка
    schemas = patch_request.schemas
    if schemas:
        schemas = [schema.replace("urn:ietf:params:scim:api:messages: 2.0:PatchOp",
                                "urn:ietf:params:scim:api:messages:2.0:PatchOp") for schema in schemas]
    
    return {
        "schemas": schemas,
        "Operations": adapted_operations
    }


@router.patch("/{user_id}", response_model=User)
async def patch_user(
    user_id: str,
    patch_request: PatchRequest,
    request: Request
) -> User:
    """Частичное обновление пользователя через PATCH операции"""
    
    try:
        headers = get_request_headers(request)
        logger.info(f"Processing PATCH request for user {user_id}")
        
        # Валидация операций
        for i, operation in enumerate(patch_request.Operations):
            logger.info(f"Operation {i+1}: op={operation.op}, path={operation.path}, value={operation.value}")
            
            # Проверяем обязательные поля
            if operation.op in ["replace", "add"] and operation.value is None and operation.path is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Operation {operation.op} requires either 'path' or 'value'"
                )
        
        # Адаптируем данные для upstream API
        patch_data = await _adapt_patch_for_upstream(patch_request, user_id, headers)
        logger.info(f"Adapted PATCH data to send upstream: {patch_data}")
        
        user = await proxy_service.patch_user(user_id, patch_data, headers)
        logger.info(f"PATCH operation successful for user {user_id}")
        return user
        
    except UpstreamError as e:
        logger.error(f"Upstream error for user {user_id}: {e}")
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Unexpected error in patch_user for user {user_id}: {e}", exc_info=True)
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