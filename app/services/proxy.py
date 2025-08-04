"""HTTP прокси сервис для взаимодействия с upstream SCIM API"""

import httpx
from typing import Dict, Any, Optional, List
import asyncio
from urllib.parse import urljoin, urlparse, parse_qs, urlencode

from ..config import settings
from ..models.scim import User, ListResponse, Group, GroupListResponse
from ..utils.exceptions import UpstreamError


class SCIMProxyService:
    """Сервис для проксирования запросов к upstream SCIM API"""
    
    def __init__(self):
        self.client: Optional[httpx.AsyncClient] = None
        self._setup_client()
    
    def _setup_client(self):
        """Настройка HTTP клиента"""
        self.client = httpx.AsyncClient(
            base_url=str(settings.upstream_base_url),
            timeout=settings.upstream_timeout,
            limits=httpx.Limits(
                max_connections=settings.upstream_max_connections,
                max_keepalive_connections=20
            ),
            follow_redirects=True
        )
    
    async def close(self):
        """Закрытие HTTP клиента"""
        if self.client:
            await self.client.aclose()
    
    async def get_users(
        self, 
        headers: Dict[str, str],
        start_index: int = 1,
        count: int = 100,
        attributes: Optional[List[str]] = None,
        excluded_attributes: Optional[List[str]] = None
    ) -> ListResponse:
        """Получение списка пользователей от upstream API"""
        
        # Подготавливаем параметры запроса
        params: Dict[str, Any] = {
            "startIndex": start_index,
            "count": count
        }
        
        if attributes:
            params["attributes"] = ",".join(attributes)
        
        if excluded_attributes:
            params["excludedAttributes"] = ",".join(excluded_attributes)
        
        try:
            if not self.client:
                raise UpstreamError("HTTP client not initialized")
                
            response = await self.client.get(
                "/Users",
                params=params,
                headers=self._prepare_headers(headers)
            )
            
            if response.status_code == 200:
                data = response.json()
                try:
                    return ListResponse(**data)
                except Exception as e:
                    raise UpstreamError(f"Failed to parse upstream response: {str(e)}")
            else:
                raise UpstreamError(
                    f"Upstream API returned {response.status_code}: {response.text}",
                    status_code=response.status_code
                )
                
        except httpx.RequestError as e:
            raise UpstreamError(f"Request to upstream API failed: {str(e)}")
        except Exception as e:
            raise UpstreamError(f"Unexpected error: {str(e)}")
    
    async def get_all_users_for_filtering(
        self,
        headers: Dict[str, str],
        max_results: Optional[int] = None,
        attributes: Optional[List[str]] = None,
        excluded_attributes: Optional[List[str]] = None
    ) -> List[User]:
        """
        Получение всех пользователей для фильтрации.
        Загружает данные порциями до достижения max_results или конца данных.
        """
        from ..config import settings
        
        if max_results is None:
            max_results = settings.max_filter_fetch_size
        
        all_users = []
        start_index = 1
        page_size = 100  # Максимальный размер страницы для upstream API
        
        while len(all_users) < max_results:
            try:
                # Запрашиваем следующую порцию
                response = await self.get_users(
                    headers=headers,
                    start_index=start_index,
                    count=page_size,
                    attributes=attributes,
                    excluded_attributes=excluded_attributes
                )
                
                # Если нет данных, прекращаем
                if not response.Resources:
                    break
                
                # Добавляем пользователей
                all_users.extend(response.Resources)
                
                # Если получили меньше чем запрашивали, значит данные закончились
                if len(response.Resources) < page_size:
                    break
                
                # Если достигли общего количества записей в upstream API
                if response.totalResults and len(all_users) >= response.totalResults:
                    break
                
                start_index += page_size
                
            except UpstreamError:
                # Если ошибка на промежуточной странице, возвращаем что есть
                break
        
        return all_users[:max_results]
    
    async def get_user(self, user_id: str, headers: Dict[str, str]) -> User:
        """Получение пользователя по ID от upstream API"""
        
        try:
            if not self.client:
                raise UpstreamError("HTTP client not initialized")
                
            response = await self.client.get(
                f"/Users/{user_id}",
                headers=self._prepare_headers(headers)
            )
            
            if response.status_code == 200:
                data = response.json()
                return User(**data)
            elif response.status_code == 404:
                raise UpstreamError(f"User {user_id} not found", status_code=404)
            else:
                raise UpstreamError(
                    f"Upstream API returned {response.status_code}: {response.text}",
                    status_code=response.status_code
                )
                
        except httpx.RequestError as e:
            raise UpstreamError(f"Request to upstream API failed: {str(e)}")
        except Exception as e:
            raise UpstreamError(f"Unexpected error: {str(e)}")
    
    async def create_user(self, user_data: Dict[str, Any], headers: Dict[str, str]) -> User:
        """Создание пользователя через upstream API"""
        
        try:
            if not self.client:
                raise UpstreamError("HTTP client not initialized")
                
            response = await self.client.post(
                "/Users",
                json=user_data,
                headers=self._prepare_headers(headers, content_type="application/scim+json")
            )
            
            if response.status_code in [201, 200]:
                data = response.json()
                return User(**data)
            else:
                raise UpstreamError(
                    f"Upstream API returned {response.status_code}: {response.text}",
                    status_code=response.status_code
                )
                
        except httpx.RequestError as e:
            raise UpstreamError(f"Request to upstream API failed: {str(e)}")
        except Exception as e:
            raise UpstreamError(f"Unexpected error: {str(e)}")
    
    async def update_user(
        self, 
        user_id: str, 
        user_data: Dict[str, Any], 
        headers: Dict[str, str]
    ) -> User:
        """Полное обновление пользователя через upstream API"""
        
        try:
            if not self.client:
                raise UpstreamError("HTTP client not initialized")
                
            response = await self.client.put(
                f"/Users/{user_id}",
                json=user_data,
                headers=self._prepare_headers(headers, content_type="application/scim+json")
            )
            
            if response.status_code == 200:
                data = response.json()
                return User(**data)
            elif response.status_code == 404:
                raise UpstreamError(f"User {user_id} not found", status_code=404)
            else:
                raise UpstreamError(
                    f"Upstream API returned {response.status_code}: {response.text}",
                    status_code=response.status_code
                )
                
        except httpx.RequestError as e:
            raise UpstreamError(f"Request to upstream API failed: {str(e)}")
        except Exception as e:
            raise UpstreamError(f"Unexpected error: {str(e)}")
    
    async def patch_user(
        self, 
        user_id: str, 
        patch_data: Dict[str, Any], 
        headers: Dict[str, str]
    ) -> User:
        """Частичное обновление пользователя через upstream API"""
        
        try:
            if not self.client:
                raise UpstreamError("HTTP client not initialized")
                
            response = await self.client.patch(
                f"/Users/{user_id}",
                json=patch_data,
                headers=self._prepare_headers(headers, content_type="application/scim+json")
            )
            
            if response.status_code == 200:
                data = response.json()
                return User(**data)
            elif response.status_code == 404:
                raise UpstreamError(f"User {user_id} not found", status_code=404)
            else:
                raise UpstreamError(
                    f"Upstream API returned {response.status_code}: {response.text}",
                    status_code=response.status_code
                )
                
        except httpx.RequestError as e:
            raise UpstreamError(f"Request to upstream API failed: {str(e)}")
        except Exception as e:
            raise UpstreamError(f"Unexpected error: {str(e)}")
    
    async def delete_user(self, user_id: str, headers: Dict[str, str]) -> bool:
        """Удаление пользователя через upstream API"""
        
        try:
            if not self.client:
                raise UpstreamError("HTTP client not initialized")
                
            response = await self.client.delete(
                f"/Users/{user_id}",
                headers=self._prepare_headers(headers)
            )
            
            if response.status_code == 204:
                return True
            elif response.status_code == 404:
                raise UpstreamError(f"User {user_id} not found", status_code=404)
            else:
                raise UpstreamError(
                    f"Upstream API returned {response.status_code}: {response.text}",
                    status_code=response.status_code
                )
                
        except httpx.RequestError as e:
            raise UpstreamError(f"Request to upstream API failed: {str(e)}")
        except Exception as e:
            raise UpstreamError(f"Unexpected error: {str(e)}")
    
    async def get_all_groups_for_filtering(
        self,
        headers: Dict[str, str],
        max_results: Optional[int] = None,
        attributes: Optional[List[str]] = None,
        excluded_attributes: Optional[List[str]] = None
    ) -> List[Group]:
        """
        Получение всех групп для фильтрации.
        Загружает данные порциями до достижения max_results или конца данных.
        """
        from ..config import settings
        
        if max_results is None:
            max_results = settings.max_filter_fetch_size
        
        all_groups = []
        start_index = 1
        page_size = 100  # Максимальный размер страницы для upstream API
        
        while len(all_groups) < max_results:
            try:
                # Запрашиваем следующую порцию
                response = await self.get_groups(
                    headers=headers,
                    start_index=start_index,
                    count=page_size,
                    attributes=attributes,
                    excluded_attributes=excluded_attributes
                )
                
                # Если нет данных, прекращаем
                if not response.Resources:
                    break
                
                # Добавляем группы
                all_groups.extend(response.Resources)
                
                # Если получили меньше чем запрашивали, значит данные закончились
                if len(response.Resources) < page_size:
                    break
                
                # Если достигли общего количества записей в upstream API
                if response.totalResults and len(all_groups) >= response.totalResults:
                    break
                
                start_index += page_size
                
            except UpstreamError:
                # Если ошибка на промежуточной странице, возвращаем что есть
                break
        
        return all_groups[:max_results]
    
    async def get_groups(
        self,
        headers: Dict[str, str],
        start_index: int = 1,
        count: int = 100,
        attributes: Optional[List[str]] = None,
        excluded_attributes: Optional[List[str]] = None
    ) -> GroupListResponse:
        """Получение списка групп от upstream API"""
        
        # Подготавливаем параметры запроса
        params: Dict[str, Any] = {
            "startIndex": start_index,
            "count": count
        }
        
        if attributes:
            params["attributes"] = ",".join(attributes)
        
        if excluded_attributes:
            params["excludedAttributes"] = ",".join(excluded_attributes)
        
        try:
            if not self.client:
                raise UpstreamError("HTTP client not initialized")
                
            response = await self.client.get(
                "/Groups",
                params=params,
                headers=self._prepare_headers(headers)
            )
            
            if response.status_code == 200:
                data = response.json()
                try:
                    return GroupListResponse(**data)
                except Exception as e:
                    raise UpstreamError(f"Failed to parse upstream response: {str(e)}")
            else:
                raise UpstreamError(
                    f"Upstream API returned {response.status_code}: {response.text}",
                    status_code=response.status_code
                )
                
        except httpx.RequestError as e:
            raise UpstreamError(f"Request to upstream API failed: {str(e)}")
        except Exception as e:
            raise UpstreamError(f"Unexpected error: {str(e)}")
    
    async def get_group(self, group_id: str, headers: Dict[str, str]) -> Group:
        """Получение группы по ID от upstream API"""
        
        try:
            if not self.client:
                raise UpstreamError("HTTP client not initialized")
                
            response = await self.client.get(
                f"/Groups/{group_id}",
                headers=self._prepare_headers(headers)
            )
            
            if response.status_code == 200:
                data = response.json()
                return Group(**data)
            elif response.status_code == 404:
                raise UpstreamError(f"Group {group_id} not found", status_code=404)
            else:
                raise UpstreamError(
                    f"Upstream API returned {response.status_code}: {response.text}",
                    status_code=response.status_code
                )
                
        except httpx.RequestError as e:
            raise UpstreamError(f"Request to upstream API failed: {str(e)}")
        except Exception as e:
            raise UpstreamError(f"Unexpected error: {str(e)}")
    
    async def create_group(self, group_data: Dict[str, Any], headers: Dict[str, str]) -> Group:
        """Создание группы через upstream API"""
        
        try:
            if not self.client:
                raise UpstreamError("HTTP client not initialized")
                
            response = await self.client.post(
                "/Groups",
                json=group_data,
                headers=self._prepare_headers(headers, content_type="application/scim+json")
            )
            
            if response.status_code in [201, 200]:
                data = response.json()
                return Group(**data)
            else:
                raise UpstreamError(
                    f"Upstream API returned {response.status_code}: {response.text}",
                    status_code=response.status_code
                )
                
        except httpx.RequestError as e:
            raise UpstreamError(f"Request to upstream API failed: {str(e)}")
        except Exception as e:
            raise UpstreamError(f"Unexpected error: {str(e)}")
    
    async def update_group(
        self,
        group_id: str,
        group_data: Dict[str, Any],
        headers: Dict[str, str]
    ) -> Group:
        """Полное обновление группы через upstream API"""
        
        try:
            if not self.client:
                raise UpstreamError("HTTP client not initialized")
                
            response = await self.client.put(
                f"/Groups/{group_id}",
                json=group_data,
                headers=self._prepare_headers(headers, content_type="application/scim+json")
            )
            
            if response.status_code == 200:
                data = response.json()
                return Group(**data)
            elif response.status_code == 404:
                raise UpstreamError(f"Group {group_id} not found", status_code=404)
            else:
                raise UpstreamError(
                    f"Upstream API returned {response.status_code}: {response.text}",
                    status_code=response.status_code
                )
                
        except httpx.RequestError as e:
            raise UpstreamError(f"Request to upstream API failed: {str(e)}")
        except Exception as e:
            raise UpstreamError(f"Unexpected error: {str(e)}")
    
    async def patch_group(
        self,
        group_id: str,
        patch_data: Dict[str, Any],
        headers: Dict[str, str]
    ) -> Group:
        """Частичное обновление группы через upstream API"""
        
        try:
            if not self.client:
                raise UpstreamError("HTTP client not initialized")
                
            response = await self.client.patch(
                f"/Groups/{group_id}",
                json=patch_data,
                headers=self._prepare_headers(headers, content_type="application/scim+json")
            )
            
            if response.status_code == 200:
                data = response.json()
                return Group(**data)
            elif response.status_code == 404:
                raise UpstreamError(f"Group {group_id} not found", status_code=404)
            else:
                raise UpstreamError(
                    f"Upstream API returned {response.status_code}: {response.text}",
                    status_code=response.status_code
                )
                
        except httpx.RequestError as e:
            raise UpstreamError(f"Request to upstream API failed: {str(e)}")
        except Exception as e:
            raise UpstreamError(f"Unexpected error: {str(e)}")
    
    async def delete_group(self, group_id: str, headers: Dict[str, str]) -> bool:
        """Удаление группы через upstream API"""
        
        try:
            if not self.client:
                raise UpstreamError("HTTP client not initialized")
                
            response = await self.client.delete(
                f"/Groups/{group_id}",
                headers=self._prepare_headers(headers)
            )
            
            if response.status_code == 204:
                return True
            elif response.status_code == 404:
                raise UpstreamError(f"Group {group_id} not found", status_code=404)
            else:
                raise UpstreamError(
                    f"Upstream API returned {response.status_code}: {response.text}",
                    status_code=response.status_code
                )
                
        except httpx.RequestError as e:
            raise UpstreamError(f"Request to upstream API failed: {str(e)}")
        except Exception as e:
            raise UpstreamError(f"Unexpected error: {str(e)}")
    
    def _prepare_headers(
        self,
        original_headers: Dict[str, str],
        content_type: Optional[str] = None
    ) -> Dict[str, str]:
        """Подготавливает заголовки для upstream запроса"""
        
        # Копируем все заголовки аутентификации и авторизации
        headers = {}
        
        # Важные заголовки для проксирования
        important_headers = [
            'authorization',
            'x-api-key',
            'x-auth-token',
            'bearer',
            'cookie',
            'x-forwarded-for',
            'x-real-ip',
            'user-agent'
        ]
        
        for key, value in original_headers.items():
            if key.lower() in important_headers:
                headers[key] = value
        
        # Устанавливаем Content-Type если указан
        if content_type:
            headers['Content-Type'] = content_type
        
        # Добавляем заголовки по умолчанию
        headers.setdefault('Accept', 'application/scim+json')
        headers.setdefault('User-Agent', 'SCIM-Proxy/1.0.0')
        
        return headers


# Глобальный экземпляр прокси сервиса
proxy_service = SCIMProxyService()