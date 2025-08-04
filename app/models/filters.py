"""Модели для SCIM фильтров"""

from pydantic import BaseModel
from typing import Optional, Any
from enum import Enum


class FilterOperator(str, Enum):
    """Операторы сравнения SCIM"""
    EQ = "eq"  # равно
    NE = "ne"  # не равно
    CO = "co"  # содержит
    SW = "sw"  # начинается с
    EW = "ew"  # заканчивается на
    GT = "gt"  # больше
    GE = "ge"  # больше или равно
    LT = "lt"  # меньше
    LE = "le"  # меньше или равно
    PR = "pr"  # присутствует (не null)


class LogicalOperator(str, Enum):
    """Логические операторы"""
    AND = "and"
    OR = "or"
    NOT = "not"


class FilterExpression(BaseModel):
    """Базовый класс для выражений фильтра"""
    
    class Config:
        extra = "forbid"


class AttributeExpression(FilterExpression):
    """Выражение для атрибута: attribute operator value"""
    attribute: str
    operator: FilterOperator
    value: Optional[Any] = None
    
    def __str__(self):
        if self.operator == FilterOperator.PR:
            return f"{self.attribute} pr"
        return f"{self.attribute} {self.operator} {repr(self.value)}"


class LogicalExpression(FilterExpression):
    """Логическое выражение: left AND/OR right или NOT expression"""
    operator: LogicalOperator
    left: Optional["FilterExpression"] = None
    right: Optional["FilterExpression"] = None
    
    def __str__(self):
        if self.operator == LogicalOperator.NOT:
            return f"not ({self.left})"
        return f"({self.left} {self.operator} {self.right})"


class GroupExpression(FilterExpression):
    """Группированное выражение: (expression)"""
    expression: "FilterExpression"
    
    def __str__(self):
        return f"({self.expression})"


class ComplexAttributeExpression(FilterExpression):
    """Сложное выражение для массивов: emails[type eq "work"].value"""
    attribute: str  # emails
    filter_expression: "FilterExpression"  # type eq "work"
    sub_attribute: Optional[str] = None  # value
    
    def __str__(self):
        result = f"{self.attribute}[{self.filter_expression}]"
        if self.sub_attribute:
            result += f".{self.sub_attribute}"
        return result


# Обновляем модели для поддержки forward references
FilterExpression.model_rebuild()
LogicalExpression.model_rebuild()
GroupExpression.model_rebuild()
ComplexAttributeExpression.model_rebuild()