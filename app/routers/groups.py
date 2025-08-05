"""Groups роутер для SCIM API"""

from fastapi import APIRouter, Query, HTTPException, Request, Depends
from typing import Optional, List, Dict, Any, Union
import logging

from ..models.scim import Group, GroupListResponse, PatchRequest, SCIMError
from ..services.proxy import proxy_service
from ..services.filter_parser import FilterParser
from ..services.filter_engine import FilterEngine
from ..utils.exceptions import (
    InvalidFilterError, 
    FilterEvaluationError, 
    UpstreamError,
    ResourceNotFoundError
)

router = APIRouter(prefix="/Groups", tags=["groups"])
logger = logging.getLogger(__name__)

# Инициализируем сервисы
filter_parser = FilterParser()
filter_engine = FilterEngine()


def get_request_headers(request: Request) -> Dict[str, str]:
    """Извлекает заголовки из запроса"""
    return dict(request.headers)


def _filter_group_attributes(group: Union[Group, Dict[str, Any]], attributes: Optional[List[str]] = None, excluded_attributes: Optional[List[str]] = None) -> Union[Group, Dict[str, Any]]:
    """Фильтрует атрибуты группы согласно SCIM спецификации"""
    
    # Если фильтрация не нужна, возвращаем как есть
    if not attributes and not excluded_attributes:
        return group
    
    # Преобразуем группу в словарь
    if isinstance(group, dict):
        group_dict = group.copy()
    elif hasattr(group, 'dict') and callable(getattr(group, 'dict')):
        group_dict = group.dict(by_alias=True, exclude_none=False)
    else:
        group_dict = group.__dict__.copy()
    
    # Если указаны конкретные атрибуты для включения
    if attributes:
        # Всегда включаем обязательные атрибуты SCIM
        required_attributes = {'id', 'schemas'}
        attributes_set = set(attributes) | required_attributes
        
        # Фильтруем только указанные атрибуты
        filtered_dict = {}
        for attr in attributes_set:
            if attr in group_dict:
                filtered_dict[attr] = group_dict[attr]
        
        return filtered_dict
    
    # Если указаны атрибуты для исключения
    if excluded_attributes:
        # Никогда не исключаем обязательные атрибуты SCIM
        required_attributes = {'id', 'schemas'}
        excluded_set = set(excluded_attributes) - required_attributes
        
        # Исключаем указанные атрибуты
        filtered_dict = group_dict.copy()
        for attr in excluded_set:
            filtered_dict.pop(attr, None)
        
        return filtered_dict
    
    # Если фильтрация не указана, возвращаем все атрибуты
    return group_dict


def _apply_group_attribute_filtering(groups: List[Union[Group, Dict[str, Any]]], attributes: Optional[List[str]] = None, excluded_attributes: Optional[List[str]] = None) -> List[Union[Group, Dict[str, Any]]]:
    """Применяет фильтрацию атрибутов к списку групп"""
    if not attributes and not excluded_attributes:
        # Если фильтрация не нужна, возвращаем как есть
        return groups
    
    filtered_groups = []
    for group in groups:
        filtered_group = _filter_group_attributes(group, attributes, excluded_attributes)
        filtered_groups.append(filtered_group)
    
    return filtered_groups


@router.get("", response_model=GroupListResponse)
async def list_groups(
    request: Request,
    filter: Optional[str] = Query(None, description="SCIM filter expression"),
    attributes: Optional[str] = Query(None, description="Comma-separated list of attributes to return"),
    excluded_attributes: Optional[str] = Query(None, alias="excludedAttributes", description="Comma-separated list of attributes to exclude"),
    sort_by: Optional[str] = Query(None, alias="sortBy", description="Attribute to sort by"),
    sort_order: Optional[str] = Query("ascending", alias="sortOrder", description="Sort order: ascending or descending"),
    start_index: int = Query(1, alias="startIndex", ge=1, description="1-based index of the first result"),
    count: int = Query(100, ge=1, le=1000, description="Number of results per page")
) -> GroupListResponse:
    """Получение списка групп с поддержкой фильтрации"""
    
    try:
        logger.info(f"Processing groups request with filter: {filter}")
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
                logger.info(f"Loading up to {max_fetch} groups for filtering")
                
                all_groups = await proxy_service.get_all_groups_for_filtering(
                    headers=headers,
                    max_results=max_fetch,
                    attributes=attributes_list,
                    excluded_attributes=excluded_attributes_list
                )
                logger.info(f"Loaded {len(all_groups)} groups for filtering")
                
                # Применяем фильтр ко всем загруженным данным
                logger.info(f"Applying filter to {len(all_groups)} groups")
                filtered_groups = filter_engine.apply_filter(all_groups, filter_expr)
                logger.info(f"Filter applied, {len(filtered_groups)} groups match")
                
                # Применяем пагинацию к отфильтрованным результатам
                start_idx = start_index - 1  # Преобразуем в 0-based индекс
                end_idx = start_idx + count
                paginated_groups = filtered_groups[start_idx:end_idx]
                
                # Применяем фильтрацию атрибутов к отфильтрованным результатам
                filtered_paginated_groups = _apply_group_attribute_filtering(list(paginated_groups), attributes_list, excluded_attributes_list)
                
                # Создаем ответ
                response = GroupListResponse(
                    schemas=["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
                    totalResults=len(filtered_groups),
                    startIndex=start_index,
                    itemsPerPage=len(filtered_paginated_groups),
                    Resources=filtered_paginated_groups
                )
                
                logger.info(f"Returning {len(paginated_groups)} groups (page {start_index}-{start_index + len(paginated_groups) - 1} of {len(filtered_groups)} total)")
                
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
            response = await proxy_service.get_groups(
                headers=headers,
                start_index=start_index,
                count=count,
                attributes=None,  # НЕ передаем в upstream API
                excluded_attributes=None  # НЕ передаем в upstream API
            )
            logger.info(f"Upstream API returned {len(response.Resources)} groups")
            
            # Применяем фильтрацию атрибутов на уровне прокси
            if attributes_list or excluded_attributes_list:
                logger.info(f"Applying attribute filtering: attributes={attributes_list}, excluded={excluded_attributes_list}")
                filtered_resources = _apply_group_attribute_filtering(response.Resources, attributes_list, excluded_attributes_list)
                
                # Создаем новый ответ с отфильтрованными атрибутами
                response = GroupListResponse(
                    schemas=response.schemas,
                    totalResults=response.totalResults,
                    startIndex=response.startIndex,
                    itemsPerPage=response.itemsPerPage,
                    Resources=filtered_resources
                )
                logger.info(f"Attribute filtering applied to {len(filtered_resources)} groups")
        
        return response
        
    except UpstreamError as e:
        logger.error(f"Upstream error: {e}", exc_info=True)
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Unexpected error in list_groups: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{group_id}", response_model=Group)
async def get_group(
    group_id: str,
    request: Request
) -> Group:
    """Получение группы по ID"""
    
    try:
        headers = get_request_headers(request)
        group = await proxy_service.get_group(group_id, headers)
        return group
        
    except UpstreamError as e:
        logger.error(f"Upstream error: {e}")
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Unexpected error in get_group: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=Group, status_code=201)
async def create_group(
    group_data: Dict[str, Any],
    request: Request
) -> Group:
    """Создание новой группы"""
    
    try:
        headers = get_request_headers(request)
        group = await proxy_service.create_group(group_data, headers)
        return group
        
    except UpstreamError as e:
        logger.error(f"Upstream error: {e}")
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Unexpected error in create_group: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{group_id}", response_model=Group)
async def update_group(
    group_id: str,
    group_data: Dict[str, Any],
    request: Request
) -> Group:
    """Полное обновление группы"""
    
    try:
        headers = get_request_headers(request)
        group = await proxy_service.update_group(group_id, group_data, headers)
        return group
        
    except UpstreamError as e:
        logger.error(f"Upstream error: {e}")
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Unexpected error in update_group: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


async def _adapt_patch_for_upstream(
    patch_request: PatchRequest,
    group_id: str,
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
            # Получаем текущие данные группы
            current_group = await proxy_service.get_group(group_id, headers)
            current_group_dict = current_group.dict() if hasattr(current_group, 'dict') else current_group.__dict__
            
            # Группируем операции по базовому пути (например, members)
            operations_by_path = {}
            for op in add_operations_to_convert:
                # Извлекаем базовый путь (например, "members" из "members[value eq \"user123\"].display")
                base_path = op.path.split('[')[0]
                if base_path not in operations_by_path:
                    operations_by_path[base_path] = []
                operations_by_path[base_path].append(op)
            
            # Обрабатываем каждый базовый путь
            for base_path, ops in operations_by_path.items():
                logger.info(f"Processing {len(ops)} add operations for path: {base_path}")
                
                # Получаем текущий массив
                current_array = current_group_dict.get(base_path, [])
                if not isinstance(current_array, list):
                    current_array = []
                
                # Применяем операции add
                updated_array = current_array.copy()
                
                for op in ops:
                    # Парсим фильтр из path (например, "value eq \"user123\"")
                    if '[' in op.path and ']' in op.path:
                        filter_part = op.path.split('[')[1].split(']')[0]
                        field_part = op.path.split('].')[1] if '].' in op.path else None
                        
                        # Простой парсинг фильтра "value eq \"user123\""
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


@router.patch("/{group_id}", response_model=Group)
async def patch_group(
    group_id: str,
    patch_request: PatchRequest,
    request: Request
) -> Group:
    """Частичное обновление группы через PATCH операции"""
    
    try:
        headers = get_request_headers(request)
        
        # Адаптируем PATCH запрос под требования upstream API
        patch_data = await _adapt_patch_for_upstream(patch_request, group_id, headers)
        
        group = await proxy_service.patch_group(group_id, patch_data, headers)
        return group
        
    except UpstreamError as e:
        logger.error(f"Upstream error: {e}")
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Unexpected error in patch_group: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{group_id}", status_code=204)
async def delete_group(
    group_id: str,
    request: Request
):
    """Удаление группы"""
    
    try:
        headers = get_request_headers(request)
        await proxy_service.delete_group(group_id, headers)
        return None
        
    except UpstreamError as e:
        logger.error(f"Upstream error: {e}")
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Unexpected error in delete_group: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")