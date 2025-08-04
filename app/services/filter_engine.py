"""Движок для применения SCIM фильтров к данным"""

from typing import List, Any, Dict, Union, TypeVar
import re

from ..models.filters import (
    FilterExpression, AttributeExpression, LogicalExpression,
    GroupExpression, ComplexAttributeExpression,
    FilterOperator, LogicalOperator
)
from ..utils.exceptions import FilterEvaluationError

# Универсальный тип для SCIM ресурсов
T = TypeVar('T')


class FilterEngine:
    """Движок для применения SCIM фильтров к данным"""
    
    def apply_filter(self, resources: List[T], filter_expr: FilterExpression) -> List[T]:
        """Применяет фильтр к списку SCIM ресурсов (пользователи, группы и т.д.)"""
        if not filter_expr:
            return resources
        
        filtered_resources = []
        for resource in resources:
            try:
                if self._evaluate_expression(resource, filter_expr):
                    filtered_resources.append(resource)
            except Exception as e:
                # Логируем ошибку, но продолжаем обработку
                resource_id = getattr(resource, 'id', 'unknown')
                print(f"Error evaluating filter for resource {resource_id}: {e}")
                continue
        
        return filtered_resources
    
    def _evaluate_expression(self, resource: Any, expr: FilterExpression) -> bool:
        """Оценивает выражение фильтра для SCIM ресурса"""
        if isinstance(expr, AttributeExpression):
            return self._evaluate_attribute_expression(resource, expr)
        
        elif isinstance(expr, LogicalExpression):
            return self._evaluate_logical_expression(resource, expr)
        
        elif isinstance(expr, GroupExpression):
            return self._evaluate_expression(resource, expr.expression)
        
        elif isinstance(expr, ComplexAttributeExpression):
            return self._evaluate_complex_attribute_expression(resource, expr)
        
        else:
            raise FilterEvaluationError(f"Unknown expression type: {type(expr)}")
    
    def _evaluate_attribute_expression(self, resource: Any, expr: AttributeExpression) -> bool:
        """Оценивает простое выражение атрибута"""
        value = self._get_attribute_value(resource, expr.attribute)
        
        if expr.operator == FilterOperator.PR:
            return value is not None
        
        if value is None:
            return False
        
        return self._compare_values(value, expr.operator, expr.value)
    
    def _evaluate_logical_expression(self, resource: Any, expr: LogicalExpression) -> bool:
        """Оценивает логическое выражение"""
        if expr.operator == LogicalOperator.NOT:
            if expr.left is None:
                raise FilterEvaluationError("NOT expression requires left operand")
            return not self._evaluate_expression(resource, expr.left)
        
        elif expr.operator == LogicalOperator.AND:
            if expr.left is None or expr.right is None:
                raise FilterEvaluationError("AND expression requires both operands")
            # Ранний выход для AND
            left_result = self._evaluate_expression(resource, expr.left)
            if not left_result:
                return False
            return self._evaluate_expression(resource, expr.right)
        
        elif expr.operator == LogicalOperator.OR:
            if expr.left is None or expr.right is None:
                raise FilterEvaluationError("OR expression requires both operands")
            # Ранний выход для OR
            left_result = self._evaluate_expression(resource, expr.left)
            if left_result:
                return True
            return self._evaluate_expression(resource, expr.right)
        
        else:
            raise FilterEvaluationError(f"Unknown logical operator: {expr.operator}")
    
    def _evaluate_complex_attribute_expression(self, resource: Any, expr: ComplexAttributeExpression) -> bool:
        """Оценивает сложное выражение атрибута (массивы)"""
        array_value = self._get_attribute_value(resource, expr.attribute)
        
        if not isinstance(array_value, list):
            return False
        
        # Проверяем каждый элемент массива
        for item in array_value:
            # Создаем временный объект для оценки фильтра
            if isinstance(item, dict):
                # Работаем с dict напрямую
                temp_resource = type('TempResource', (), item)()
            else:
                temp_resource = item
            
            if self._evaluate_expression(temp_resource, expr.filter_expression):
                # Если есть под-атрибут, проверяем его
                if expr.sub_attribute:
                    sub_value = self._get_attribute_value(temp_resource, expr.sub_attribute)
                    return sub_value is not None
                return True
        
        return False
    
    def _get_attribute_value(self, resource: Any, attribute_path: str) -> Any:
        """Получает значение атрибута по пути (поддерживает вложенные атрибуты)"""
        try:
            # Преобразуем ресурс в словарь для удобства
            if hasattr(resource, 'dict') and callable(getattr(resource, 'dict')):
                # Pydantic модель
                resource_dict = resource.dict(by_alias=True)
            elif hasattr(resource, '__dict__'):
                resource_dict = resource.__dict__
            elif isinstance(resource, dict):
                resource_dict = resource
            else:
                return None
            
            # Разбиваем путь на части
            parts = attribute_path.split('.')
            current_value = resource_dict
            
            for part in parts:
                if isinstance(current_value, dict):
                    current_value = current_value.get(part)
                else:
                    return None
                
                if current_value is None:
                    return None
            
            return current_value
            
        except Exception:
            return None
    
    def _compare_values(self, actual: Any, operator: FilterOperator, expected: Any) -> bool:
        """Сравнивает значения согласно оператору"""
        try:
            if operator == FilterOperator.EQ:
                return self._equals(actual, expected)
            
            elif operator == FilterOperator.NE:
                return not self._equals(actual, expected)
            
            elif operator == FilterOperator.CO:
                return self._contains(actual, expected)
            
            elif operator == FilterOperator.SW:
                return self._starts_with(actual, expected)
            
            elif operator == FilterOperator.EW:
                return self._ends_with(actual, expected)
            
            elif operator == FilterOperator.GT:
                return self._greater_than(actual, expected)
            
            elif operator == FilterOperator.GE:
                return self._greater_equal(actual, expected)
            
            elif operator == FilterOperator.LT:
                return self._less_than(actual, expected)
            
            elif operator == FilterOperator.LE:
                return self._less_equal(actual, expected)
            
            else:
                raise FilterEvaluationError(f"Unknown operator: {operator}")
                
        except Exception as e:
            raise FilterEvaluationError(f"Error comparing values: {e}")
    
    def _equals(self, actual: Any, expected: Any) -> bool:
        """Проверка на равенство"""
        if isinstance(actual, str) and isinstance(expected, str):
            return actual.lower() == expected.lower()  # Case-insensitive для строк
        return actual == expected
    
    def _contains(self, actual: Any, expected: Any) -> bool:
        """Проверка на содержание"""
        if not isinstance(actual, str) or not isinstance(expected, str):
            return False
        return expected.lower() in actual.lower()
    
    def _starts_with(self, actual: Any, expected: Any) -> bool:
        """Проверка на начало строки"""
        if not isinstance(actual, str) or not isinstance(expected, str):
            return False
        return actual.lower().startswith(expected.lower())
    
    def _ends_with(self, actual: Any, expected: Any) -> bool:
        """Проверка на окончание строки"""
        if not isinstance(actual, str) or not isinstance(expected, str):
            return False
        return actual.lower().endswith(expected.lower())
    
    def _greater_than(self, actual: Any, expected: Any) -> bool:
        """Проверка больше"""
        try:
            return float(actual) > float(expected)
        except (ValueError, TypeError):
            return False
    
    def _greater_equal(self, actual: Any, expected: Any) -> bool:
        """Проверка больше или равно"""
        try:
            return float(actual) >= float(expected)
        except (ValueError, TypeError):
            return False
    
    def _less_than(self, actual: Any, expected: Any) -> bool:
        """Проверка меньше"""
        try:
            return float(actual) < float(expected)
        except (ValueError, TypeError):
            return False
    
    def _less_equal(self, actual: Any, expected: Any) -> bool:
        """Проверка меньше или равно"""
        try:
            return float(actual) <= float(expected)
        except (ValueError, TypeError):
            return False