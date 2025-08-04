"""Парсер SCIM фильтров согласно RFC 7644"""

import re
from typing import Optional, List, Tuple, Any

from ..models.filters import (
    FilterExpression, AttributeExpression, LogicalExpression, 
    GroupExpression, ComplexAttributeExpression,
    FilterOperator, LogicalOperator
)
from ..utils.exceptions import InvalidFilterError


class FilterParser:
    """Парсер SCIM фильтров согласно RFC 7644"""
    
    # Регулярные выражения для токенов
    TOKEN_PATTERNS = [
        ('OPERATOR', r'\b(?:eq|ne|co|sw|ew|gt|ge|lt|le|pr)\b'),
        ('LOGICAL', r'\b(?:and|or|not)\b'),
        ('BOOLEAN', r'\b(?:true|false)\b'),
        ('NULL', r'\bnull\b'),
        ('ATTRIBUTE', r'[a-zA-Z][a-zA-Z0-9_]*(?:\.[a-zA-Z][a-zA-Z0-9_]*)*'),
        ('STRING', r'"(?:[^"\\]|\\.)*"'),
        ('NUMBER', r'-?\d+(?:\.\d+)?'),
        ('LPAREN', r'\('),
        ('RPAREN', r'\)'),
        ('LBRACKET', r'\['),
        ('RBRACKET', r'\]'),
        ('DOT', r'\.'),
        ('WHITESPACE', r'\s+'),
    ]
    
    def __init__(self):
        self.tokens: List[Tuple[str, str]] = []
        self.position: int = 0
        
    def parse(self, filter_string: str) -> FilterExpression:
        """Парсит строку фильтра и возвращает AST"""
        if not filter_string or not filter_string.strip():
            raise InvalidFilterError("Empty filter string")
            
        self.tokens = self._tokenize(filter_string)
        self.position = 0
        
        try:
            expression = self._parse_logical_or()
            if self.position < len(self.tokens):
                raise InvalidFilterError(f"Unexpected token: {self.tokens[self.position]}")
            return expression
        except IndexError:
            raise InvalidFilterError("Unexpected end of filter")
    
    def _tokenize(self, filter_string: str) -> List[Tuple[str, str]]:
        """Разбивает строку на токены"""
        tokens = []
        position = 0
        
        while position < len(filter_string):
            matched = False
            
            for token_type, pattern in self.TOKEN_PATTERNS:
                regex = re.compile(pattern, re.IGNORECASE)
                match = regex.match(filter_string, position)
                
                if match:
                    value = match.group(0)
                    if token_type != 'WHITESPACE':  # Игнорируем пробелы
                        tokens.append((token_type, value))
                    position = match.end()
                    matched = True
                    break
            
            if not matched:
                raise InvalidFilterError(f"Invalid character at position {position}: {filter_string[position]}")
        
        return tokens
    
    def _current_token(self) -> Optional[Tuple[str, str]]:
        """Возвращает текущий токен"""
        if self.position < len(self.tokens):
            return self.tokens[self.position]
        return None
    
    def _consume_token(self, expected_type: Optional[str] = None) -> Tuple[str, str]:
        """Потребляет текущий токен"""
        if self.position >= len(self.tokens):
            raise InvalidFilterError("Unexpected end of filter")
        
        token = self.tokens[self.position]
        self.position += 1
        
        if expected_type and token[0] != expected_type:
            raise InvalidFilterError(f"Expected {expected_type}, got {token[0]}")
        
        return token
    
    def _parse_logical_or(self) -> FilterExpression:
        """Парсит OR выражения (наименьший приоритет)"""
        left = self._parse_logical_and()
        
        current = self._current_token()
        while (current and
               current[0] == 'LOGICAL' and
               current[1].lower() == 'or'):
            self._consume_token('LOGICAL')
            right = self._parse_logical_and()
            left = LogicalExpression(operator=LogicalOperator.OR, left=left, right=right)
            current = self._current_token()
        
        return left
    
    def _parse_logical_and(self) -> FilterExpression:
        """Парсит AND выражения"""
        left = self._parse_logical_not()
        
        current = self._current_token()
        while (current and
               current[0] == 'LOGICAL' and
               current[1].lower() == 'and'):
            self._consume_token('LOGICAL')
            right = self._parse_logical_not()
            left = LogicalExpression(operator=LogicalOperator.AND, left=left, right=right)
            current = self._current_token()
        
        return left
    
    def _parse_logical_not(self) -> FilterExpression:
        """Парсит NOT выражения"""
        current = self._current_token()
        if (current and
            current[0] == 'LOGICAL' and
            current[1].lower() == 'not'):
            self._consume_token('LOGICAL')
            expression = self._parse_primary()
            return LogicalExpression(operator=LogicalOperator.NOT, left=expression)
        
        return self._parse_primary()
    
    def _parse_primary(self) -> FilterExpression:
        """Парсит первичные выражения"""
        token = self._current_token()
        
        if not token:
            raise InvalidFilterError("Unexpected end of filter")
        
        # Группированное выражение
        if token[0] == 'LPAREN':
            self._consume_token('LPAREN')
            expression = self._parse_logical_or()
            self._consume_token('RPAREN')
            return GroupExpression(expression=expression)
        
        # Атрибут
        if token[0] == 'ATTRIBUTE':
            return self._parse_attribute_expression()
        
        raise InvalidFilterError(f"Unexpected token: {token}")
    
    def _parse_attribute_expression(self) -> FilterExpression:
        """Парсит выражения с атрибутами"""
        attribute_token = self._consume_token('ATTRIBUTE')
        attribute = attribute_token[1]
        
        # Проверяем на сложный атрибут (массив)
        current = self._current_token()
        if (current and current[0] == 'LBRACKET'):
            return self._parse_complex_attribute(attribute)
        
        # Простое выражение атрибута
        operator_token = self._consume_token('OPERATOR')
        operator = FilterOperator(operator_token[1].lower())
        
        # Для оператора pr значение не нужно
        if operator == FilterOperator.PR:
            return AttributeExpression(attribute=attribute, operator=operator)
        
        # Парсим значение
        value = self._parse_value()
        return AttributeExpression(attribute=attribute, operator=operator, value=value)
    
    def _parse_complex_attribute(self, attribute: str) -> ComplexAttributeExpression:
        """Парсит сложные атрибуты типа emails[type eq "work"].value"""
        self._consume_token('LBRACKET')
        filter_expression = self._parse_logical_or()
        self._consume_token('RBRACKET')
        
        # Проверяем на под-атрибут
        sub_attribute = None
        current = self._current_token()
        if (current and current[0] == 'DOT'):
            self._consume_token('DOT')
            sub_attr_token = self._consume_token('ATTRIBUTE')
            sub_attribute = sub_attr_token[1]
        
        return ComplexAttributeExpression(
            attribute=attribute,
            filter_expression=filter_expression,
            sub_attribute=sub_attribute
        )
    
    def _parse_value(self) -> Any:
        """Парсит значения"""
        token = self._current_token()
        
        if not token:
            raise InvalidFilterError("Expected value")
        
        if token[0] == 'STRING':
            self._consume_token('STRING')
            # Убираем кавычки и обрабатываем escape-последовательности
            return token[1][1:-1].replace('\\"', '"').replace('\\\\', '\\')
        
        elif token[0] == 'NUMBER':
            self._consume_token('NUMBER')
            value = token[1]
            return float(value) if '.' in value else int(value)
        
        elif token[0] == 'BOOLEAN':
            self._consume_token('BOOLEAN')
            return token[1].lower() == 'true'
        
        elif token[0] == 'NULL':
            self._consume_token('NULL')
            return None
        
        else:
            raise InvalidFilterError(f"Expected value, got {token[0]}")