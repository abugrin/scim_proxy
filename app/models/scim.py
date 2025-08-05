"""SCIM модели данных согласно RFC 7644"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum


class SCIMSchema(str, Enum):
    """SCIM схемы"""
    USER = "urn:ietf:params:scim:schemas:core:2.0:User"
    LIST_RESPONSE = "urn:ietf:params:scim:api:messages:2.0:ListResponse"
    PATCH_OP = "urn:ietf:params:scim:api:messages:2.0:PatchOp"
    ERROR = "urn:ietf:params:scim:api:messages:2.0:Error"
    YANDEX_USER_EXT = "urn:ietf:params:scim:schemas:extension:yandex360:2.0:User"
    GROUP = "urn:ietf:params:scim:schemas:core:2.0:Group"


class Email(BaseModel):
    """Email адрес пользователя"""
    value: str
    type: Optional[str] = None
    primary: Optional[bool] = False


class PhoneNumber(BaseModel):
    """Номер телефона пользователя"""
    value: str
    type: Optional[str] = None
    primary: Optional[bool] = False


class Name(BaseModel):
    """Имя пользователя"""
    formatted: Optional[str] = None
    familyName: Optional[str] = None
    givenName: Optional[str] = None
    middleName: Optional[str] = None
    honorificPrefix: Optional[str] = None
    honorificSuffix: Optional[str] = None


class Meta(BaseModel):
    """Метаданные ресурса"""
    resourceType: Optional[str] = None
    created: Optional[datetime] = None
    lastModified: Optional[datetime] = None
    location: Optional[str] = None
    version: Optional[str] = None


class YandexUserExtension(BaseModel):
    """Расширение Yandex 360 для пользователя"""
    aliases: List[Dict[str, str]] = Field(default_factory=list)


class User(BaseModel):
    """Пользователь SCIM"""
    id: Optional[str] = None
    externalId: Optional[str] = None
    userName: Optional[str] = None
    displayName: Optional[str] = None
    active: Optional[bool] = True
    emails: List[Email] = Field(default_factory=list)
    phoneNumbers: List[PhoneNumber] = Field(default_factory=list)
    name: Optional[Name] = None
    title: Optional[str] = None
    isInternalRobot: Optional[bool] = False
    meta: Optional[Meta] = None
    schemas: List[str] = Field(default_factory=lambda: [SCIMSchema.USER])
    
    # Yandex 360 extension
    yandex_extension: Optional[YandexUserExtension] = Field(
        None, 
        alias="urn:ietf:params:scim:schemas:extension:yandex360:2.0:User"
    )
    
    class Config:
        populate_by_name = True
        extra = "allow"  # Разрешаем дополнительные поля


class ListResponse(BaseModel):
    """Ответ со списком ресурсов SCIM"""
    schemas: List[str] = Field(default_factory=lambda: [SCIMSchema.LIST_RESPONSE])
    totalResults: int
    startIndex: int = 1
    itemsPerPage: int
    Resources: List[Union[User, Dict[str, Any]]] = Field(default_factory=list)


class SCIMError(BaseModel):
    """Ошибка SCIM"""
    schemas: List[str] = Field(default_factory=lambda: [SCIMSchema.ERROR])
    status: int
    scimType: Optional[str] = None
    detail: Optional[str] = None


class PatchOperation(BaseModel):
    """PATCH операция SCIM"""
    op: str  # add, remove, replace
    path: Optional[str] = None
    value: Optional[Any] = None


class PatchRequest(BaseModel):
    """PATCH запрос SCIM"""
    schemas: List[str] = Field(default_factory=lambda: [SCIMSchema.PATCH_OP])
    Operations: List[PatchOperation]


class GroupMember(BaseModel):
    """Член группы SCIM"""
    value: str  # ID пользователя или группы
    ref: Optional[str] = Field(None, alias="$ref")  # URI ссылка на ресурс
    type: Optional[str] = None  # User или Group
    display: Optional[str] = None  # Отображаемое имя


class Group(BaseModel):
    """Группа SCIM"""
    id: Optional[str] = None
    externalId: Optional[str] = None
    displayName: str
    members: List[GroupMember] = Field(default_factory=list)
    meta: Optional[Meta] = None
    schemas: List[str] = Field(default_factory=lambda: [SCIMSchema.GROUP])
    
    class Config:
        populate_by_name = True
        extra = "allow"  # Разрешаем дополнительные поля


class GroupListResponse(BaseModel):
    """Ответ со списком групп SCIM"""
    schemas: List[str] = Field(default_factory=lambda: [SCIMSchema.LIST_RESPONSE])
    totalResults: int
    startIndex: int = 1
    itemsPerPage: int
    Resources: List[Union[Group, Dict[str, Any]]] = Field(default_factory=list)