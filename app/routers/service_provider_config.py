"""ServiceProviderConfig роутер для SCIM API"""

from fastapi import APIRouter
from typing import Dict, Any

router = APIRouter(tags=["service-provider-config"])


@router.get("/ServiceProviderConfig")
async def get_service_provider_config() -> Dict[str, Any]:
    """Возвращает конфигурацию SCIM сервиса согласно RFC 7644"""
    
    return {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig"],
        "documentationUri": "https://tools.ietf.org/html/rfc7644",
        "patch": {
            "supported": True
        },
        "bulk": {
            "supported": False,
            "maxOperations": 0,
            "maxPayloadSize": 0
        },
        "filter": {
            "supported": True,
            "maxResults": 1000
        },
        "changePassword": {
            "supported": False
        },
        "sort": {
            "supported": True
        },
        "etag": {
            "supported": False
        },
        "authenticationSchemes": [
            {
                "type": "httpbasic",
                "name": "HTTP Basic",
                "description": "Authentication scheme using the HTTP Basic Standard",
                "specUri": "https://tools.ietf.org/html/rfc2617",
                "documentationUri": "https://example.com/help/httpBasic.html"
            },
            {
                "type": "oauthbearertoken",
                "name": "OAuth Bearer Token",
                "description": "Authentication scheme using the OAuth Bearer Token Standard",
                "specUri": "https://tools.ietf.org/html/rfc6750",
                "documentationUri": "https://example.com/help/oauth.html"
            }
        ],
        "meta": {
            "location": "/v2/ServiceProviderConfig",
            "resourceType": "ServiceProviderConfig",
            "created": "2024-01-01T00:00:00Z",
            "lastModified": "2024-01-01T00:00:00Z",
            "version": "v1"
        }
    }