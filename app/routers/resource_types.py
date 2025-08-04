"""ResourceTypes роутер для SCIM API"""

from fastapi import APIRouter
from typing import Dict, Any, List

router = APIRouter(tags=["resource-types"])


@router.get("/ResourceTypes")
async def get_resource_types() -> Dict[str, Any]:
    """Возвращает список поддерживаемых типов ресурсов согласно RFC 7644"""
    
    return {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
        "totalResults": 2,
        "startIndex": 1,
        "itemsPerPage": 2,
        "Resources": [
            {
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ResourceType"],
                "id": "User",
                "name": "User",
                "endpoint": "/Users",
                "description": "User Account",
                "schema": "urn:ietf:params:scim:schemas:core:2.0:User",
                "schemaExtensions": [
                    {
                        "schema": "urn:ietf:params:scim:schemas:extension:yandex360:2.0:User",
                        "required": False
                    }
                ],
                "meta": {
                    "location": "/v2/ResourceTypes/User",
                    "resourceType": "ResourceType"
                }
            },
            {
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ResourceType"],
                "id": "Group",
                "name": "Group",
                "endpoint": "/Groups",
                "description": "Group",
                "schema": "urn:ietf:params:scim:schemas:core:2.0:Group",
                "meta": {
                    "location": "/v2/ResourceTypes/Group",
                    "resourceType": "ResourceType"
                }
            }
        ]
    }


@router.get("/ResourceTypes/User")
async def get_user_resource_type() -> Dict[str, Any]:
    """Возвращает информацию о типе ресурса User"""
    
    return {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ResourceType"],
        "id": "User",
        "name": "User",
        "endpoint": "/Users",
        "description": "User Account",
        "schema": "urn:ietf:params:scim:schemas:core:2.0:User",
        "schemaExtensions": [
            {
                "schema": "urn:ietf:params:scim:schemas:extension:yandex360:2.0:User",
                "required": False
            }
        ],
        "meta": {
            "location": "/v2/ResourceTypes/User",
            "resourceType": "ResourceType"
        }
    }


@router.get("/ResourceTypes/Group")
async def get_group_resource_type() -> Dict[str, Any]:
    """Возвращает информацию о типе ресурса Group"""
    
    return {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ResourceType"],
        "id": "Group",
        "name": "Group",
        "endpoint": "/Groups",
        "description": "Group",
        "schema": "urn:ietf:params:scim:schemas:core:2.0:Group",
        "meta": {
            "location": "/v2/ResourceTypes/Group",
            "resourceType": "ResourceType"
        }
    }