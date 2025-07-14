"""
Secure query builder for SQL injection prevention

This module provides utilities for building secure database queries with
parameterization, validation, and injection detection.
"""

import re
import hashlib
from typing import Any, Dict, List, Optional, Tuple, Union, Set
from sqlalchemy import text, select, insert, update, delete
from sqlalchemy.orm import Query
from sqlalchemy.sql import ClauseElement
from sqlalchemy.sql.expression import TextClause
import structlog

logger = structlog.get_logger(__name__)

# SQL injection patterns for detection
SQL_INJECTION_PATTERNS = [
    # Union-based injection
    r'\bunion\b.*\bselect\b',
    r'\bunion\b.*\bfrom\b',
    
    # Boolean-based injection
    r'\bor\b.*[\'"].*[\'"].*=.*[\'"].*[\'"]',
    r'\band\b.*[\'"].*[\'"].*=.*[\'"].*[\'"]',
    r'\bor\b.*\d+.*=.*\d+',
    r'\band\b.*\d+.*=.*\d+',
    
    # Time-based injection
    r'\bwaitfor\b.*\bdelay\b',
    r'\bsleep\s*\(',
    r'\bbenchmark\s*\(',
    
    # Error-based injection
    r'\bcast\s*\(.*\bas\b.*\bint\b.*\)',
    r'\bconvert\s*\(.*,.*\)',
    r'\bextractvalue\s*\(',
    r'\bupdatexml\s*\(',
    
    # Stacked queries
    r';\s*drop\b',
    r';\s*delete\b',
    r';\s*insert\b',
    r';\s*update\b',
    r';\s*create\b',
    r';\s*alter\b',
    
    # Information gathering
    r'\binformation_schema\b',
    r'\bsysobjects\b',
    r'\bsyscolumns\b',
    r'\bsys\.tables\b',
    r'\bsys\.columns\b',
    
    # Function-based injection
    r'\bchar\s*\(\d+\)',
    r'\bascii\s*\(',
    r'\bsubstring\s*\(',
    r'\bmid\s*\(',
    r'\bleft\s*\(',
    r'\bright\s*\(',
    
    # Comment-based injection
    r'--.*',
    r'/\*.*\*/',
    r'#.*',
    
    # Hex encoding
    r'0x[0-9a-f]+',
    
    # Database-specific functions
    r'\bversion\s*\(\)',
    r'\buser\s*\(\)',
    r'\bdatabase\s*\(\)',
    r'\bschema\s*\(\)',
    
    # Stored procedures
    r'\bexec\s*\(',
    r'\bexecute\s*\(',
    r'\bsp_\w+',
    r'\bxp_\w+',
]

# Dangerous SQL keywords
DANGEROUS_KEYWORDS = {
    'drop', 'delete', 'truncate', 'alter', 'create', 'exec', 'execute',
    'sp_', 'xp_', 'waitfor', 'delay', 'sleep', 'benchmark'
}

# Safe operators for dynamic queries
SAFE_OPERATORS = {
    '=', '!=', '<>', '<', '>', '<=', '>=', 'like', 'ilike', 'in', 'not in',
    'is null', 'is not null', 'between', 'not between'
}

# Safe column name pattern
SAFE_COLUMN_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')


class SQLInjectionError(Exception):
    """Exception raised when SQL injection is detected"""
    pass


class QuerySecurityError(Exception):
    """Exception raised when query security validation fails"""
    pass


class SecureQueryBuilder:
    """Secure query builder with injection prevention"""
    
    def __init__(self, enable_logging: bool = True):
        self.enable_logging = enable_logging
        self.injection_pattern = re.compile(
            '|'.join(SQL_INJECTION_PATTERNS),
            re.IGNORECASE | re.MULTILINE
        )
    
    def validate_query_string(self, query: str) -> bool:
        """
        Validate query string for SQL injection patterns
        
        Args:
            query: SQL query string to validate
            
        Returns:
            bool: True if query is safe
            
        Raises:
            SQLInjectionError: If injection patterns are detected
        """
        if not query:
            return True
        
        # Check for injection patterns
        matches = self.injection_pattern.findall(query.lower())
        if matches:
            logger.error(
                "SQL injection patterns detected",
                query_hash=hashlib.sha256(query.encode()).hexdigest()[:16],
                patterns=matches[:5]  # Log first 5 matches
            )
            raise SQLInjectionError(f"SQL injection patterns detected: {matches[:3]}")
        
        # Check for dangerous keywords in unexpected contexts
        query_lower = query.lower()
        for keyword in DANGEROUS_KEYWORDS:
            if keyword in query_lower:
                # Allow keywords in comments or string literals
                if not self._is_keyword_safe_context(query_lower, keyword):
                    logger.warning(
                        "Dangerous SQL keyword detected",
                        keyword=keyword,
                        query_hash=hashlib.sha256(query.encode()).hexdigest()[:16]
                    )
                    # Don't raise error for keywords, just log warning
        
        return True
    
    def _is_keyword_safe_context(self, query: str, keyword: str) -> bool:
        """Check if keyword appears in safe context (comments, strings)"""
        # Simple check - in production, use proper SQL parser
        keyword_positions = [m.start() for m in re.finditer(re.escape(keyword), query)]
        
        for pos in keyword_positions:
            # Check if keyword is in string literal
            before_text = query[:pos]
            single_quotes = before_text.count("'") - before_text.count("\\'")
            double_quotes = before_text.count('"') - before_text.count('\\"')
            
            # If odd number of quotes, we're inside a string
            if single_quotes % 2 == 1 or double_quotes % 2 == 1:
                continue
            
            # Check if keyword is in comment
            if '--' in before_text.split('\n')[-1]:
                continue
            
            # If we reach here, keyword is in unsafe context
            return False
        
        return True
    
    def validate_column_name(self, column_name: str) -> str:
        """
        Validate column name for safety
        
        Args:
            column_name: Column name to validate
            
        Returns:
            str: Validated column name
            
        Raises:
            QuerySecurityError: If column name is invalid
        """
        if not column_name:
            raise QuerySecurityError("Column name cannot be empty")
        
        # Check for safe pattern
        if not SAFE_COLUMN_PATTERN.match(column_name):
            raise QuerySecurityError(f"Invalid column name: {column_name}")
        
        # Check length
        if len(column_name) > 64:  # Standard SQL identifier limit
            raise QuerySecurityError("Column name too long")
        
        # Check for SQL keywords (basic check)
        sql_keywords = {
            'select', 'from', 'where', 'insert', 'update', 'delete', 'drop',
            'create', 'alter', 'table', 'index', 'view', 'database', 'schema'
        }
        
        if column_name.lower() in sql_keywords:
            logger.warning("Column name is SQL keyword", column=column_name)
            # Don't raise error, just log warning
        
        return column_name
    
    def validate_operator(self, operator: str) -> str:
        """
        Validate SQL operator for safety
        
        Args:
            operator: SQL operator to validate
            
        Returns:
            str: Validated operator
            
        Raises:
            QuerySecurityError: If operator is invalid
        """
        if not operator:
            raise QuerySecurityError("Operator cannot be empty")
        
        operator_lower = operator.lower().strip()
        
        if operator_lower not in SAFE_OPERATORS:
            raise QuerySecurityError(f"Unsafe operator: {operator}")
        
        return operator_lower
    
    def build_where_clause(
        self,
        conditions: List[Dict[str, Any]],
        logic_operator: str = "AND"
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Build secure WHERE clause with parameterized values
        
        Args:
            conditions: List of condition dictionaries
            logic_operator: Logic operator (AND/OR)
            
        Returns:
            Tuple of (where_clause, parameters)
            
        Raises:
            QuerySecurityError: If conditions are invalid
        """
        if not conditions:
            return "", {}
        
        # Validate logic operator
        if logic_operator.upper() not in ['AND', 'OR']:
            raise QuerySecurityError(f"Invalid logic operator: {logic_operator}")
        
        where_parts = []
        parameters = {}
        param_counter = 0
        
        for condition in conditions:
            if not isinstance(condition, dict):
                raise QuerySecurityError("Condition must be a dictionary")
            
            column = condition.get('column')
            operator = condition.get('operator', '=')
            value = condition.get('value')
            
            if not column:
                raise QuerySecurityError("Condition must have 'column' field")
            
            # Validate column and operator
            safe_column = self.validate_column_name(column)
            safe_operator = self.validate_operator(operator)
            
            # Create parameter name
            param_name = f"param_{param_counter}"
            param_counter += 1
            
            # Handle different operators
            if safe_operator in ['is null', 'is not null']:
                where_parts.append(f"{safe_column} {safe_operator}")
            elif safe_operator in ['in', 'not in']:
                if not isinstance(value, (list, tuple)):
                    raise QuerySecurityError(f"Value for '{safe_operator}' must be a list")
                
                if not value:
                    # Empty list - handle appropriately
                    if safe_operator == 'in':
                        where_parts.append("1=0")  # Always false
                    else:
                        where_parts.append("1=1")  # Always true
                else:
                    placeholders = []
                    for i, item in enumerate(value):
                        item_param = f"{param_name}_{i}"
                        placeholders.append(f":{item_param}")
                        parameters[item_param] = item
                    
                    where_parts.append(f"{safe_column} {safe_operator} ({','.join(placeholders)})")
            elif safe_operator == 'between':
                if not isinstance(value, (list, tuple)) or len(value) != 2:
                    raise QuerySecurityError("Value for 'between' must be a list of 2 items")
                
                param_name_1 = f"{param_name}_1"
                param_name_2 = f"{param_name}_2"
                where_parts.append(f"{safe_column} between :{param_name_1} and :{param_name_2}")
                parameters[param_name_1] = value[0]
                parameters[param_name_2] = value[1]
            else:
                # Standard operators
                where_parts.append(f"{safe_column} {safe_operator} :{param_name}")
                parameters[param_name] = value
        
        where_clause = f" {logic_operator.upper()} ".join(where_parts)
        
        if self.enable_logging:
            logger.debug(
                "Built secure WHERE clause",
                clause=where_clause,
                param_count=len(parameters)
            )
        
        return where_clause, parameters
    
    def build_order_clause(self, order_by: List[Dict[str, str]]) -> str:
        """
        Build secure ORDER BY clause
        
        Args:
            order_by: List of order specifications
            
        Returns:
            str: ORDER BY clause
            
        Raises:
            QuerySecurityError: If order specification is invalid
        """
        if not order_by:
            return ""
        
        order_parts = []
        
        for order_spec in order_by:
            if not isinstance(order_spec, dict):
                raise QuerySecurityError("Order specification must be a dictionary")
            
            column = order_spec.get('column')
            direction = order_spec.get('direction', 'ASC').upper()
            
            if not column:
                raise QuerySecurityError("Order specification must have 'column' field")
            
            # Validate column
            safe_column = self.validate_column_name(column)
            
            # Validate direction
            if direction not in ['ASC', 'DESC']:
                raise QuerySecurityError(f"Invalid order direction: {direction}")
            
            order_parts.append(f"{safe_column} {direction}")
        
        return "ORDER BY " + ", ".join(order_parts)
    
    def create_safe_text_query(
        self,
        query_template: str,
        parameters: Dict[str, Any]
    ) -> TextClause:
        """
        Create safe text query with validation
        
        Args:
            query_template: SQL query template with named parameters
            parameters: Query parameters
            
        Returns:
            TextClause: Safe SQLAlchemy text query
            
        Raises:
            SQLInjectionError: If query contains injection patterns
        """
        # Validate query template
        self.validate_query_string(query_template)
        
        # Validate parameters
        for key, value in parameters.items():
            if isinstance(value, str):
                # Check parameter values for injection patterns
                try:
                    self.validate_query_string(value)
                except SQLInjectionError:
                    logger.error(
                        "SQL injection in parameter value",
                        parameter=key,
                        value_hash=hashlib.sha256(str(value).encode()).hexdigest()[:16]
                    )
                    raise
        
        # Create text query
        query = text(query_template)
        
        if self.enable_logging:
            logger.info(
                "Created safe text query",
                query_hash=hashlib.sha256(query_template.encode()).hexdigest()[:16],
                param_count=len(parameters)
            )
        
        return query


# Global secure query builder instance
secure_query_builder = SecureQueryBuilder()

# Convenience functions
def validate_sql_query(query: str) -> bool:
    """Validate SQL query using global builder"""
    return secure_query_builder.validate_query_string(query)

def build_safe_where_clause(
    conditions: List[Dict[str, Any]],
    logic_operator: str = "AND"
) -> Tuple[str, Dict[str, Any]]:
    """Build safe WHERE clause using global builder"""
    return secure_query_builder.build_where_clause(conditions, logic_operator)

def create_safe_query(
    query_template: str,
    parameters: Dict[str, Any]
) -> TextClause:
    """Create safe text query using global builder"""
    return secure_query_builder.create_safe_text_query(query_template, parameters)


# Export main classes and functions
__all__ = [
    'SecureQueryBuilder',
    'SQLInjectionError',
    'QuerySecurityError',
    'validate_sql_query',
    'build_safe_where_clause',
    'create_safe_query',
    'secure_query_builder'
]
