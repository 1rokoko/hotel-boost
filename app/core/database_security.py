"""
Database security configuration and utilities

This module provides enhanced database security settings, query auditing,
and SQL injection prevention mechanisms for SQLAlchemy ORM.
"""

import time
import hashlib
from typing import Any, Dict, List, Optional, Set, Callable
from sqlalchemy import event, Engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session
from sqlalchemy.pool import Pool
import structlog

from app.utils.query_builder import SecureQueryBuilder, SQLInjectionError

logger = structlog.get_logger(__name__)


class DatabaseSecurityConfig:
    """Configuration for database security settings"""
    
    def __init__(self):
        # Query auditing settings
        self.enable_query_auditing = True
        self.log_all_queries = False  # Only in development
        self.log_slow_queries = True
        self.slow_query_threshold = 1.0  # seconds
        
        # SQL injection prevention
        self.enable_injection_detection = True
        self.strict_injection_prevention = False  # Raise errors vs warnings
        self.audit_raw_queries = True
        
        # Connection security
        self.enable_connection_auditing = True
        self.max_connection_lifetime = 3600  # 1 hour
        self.enable_ssl_enforcement = True
        
        # Query complexity limits
        self.max_query_length = 10000  # characters
        self.max_joins = 10
        self.max_subqueries = 5
        
        # Monitoring and alerting
        self.enable_security_alerts = True
        self.alert_on_injection_attempts = True
        self.alert_on_suspicious_queries = True


class DatabaseSecurityMonitor:
    """Monitor database operations for security issues"""
    
    def __init__(self, config: DatabaseSecurityConfig):
        self.config = config
        self.query_builder = SecureQueryBuilder()
        self.query_stats = {
            'total_queries': 0,
            'injection_attempts': 0,
            'slow_queries': 0,
            'failed_queries': 0
        }
        self.suspicious_patterns = [
            r'\bunion\b.*\bselect\b',
            r'\bor\b.*\d+.*=.*\d+',
            r'\bwaitfor\b.*\bdelay\b',
            r'\binformation_schema\b',
            r'--.*',
            r'/\*.*\*/',
        ]
    
    def audit_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
        execution_time: Optional[float] = None,
        connection_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Audit database query for security and performance
        
        Args:
            query: SQL query string
            parameters: Query parameters
            execution_time: Query execution time in seconds
            connection_info: Connection information
            
        Returns:
            Dict with audit results
        """
        audit_result = {
            'timestamp': time.time(),
            'query_hash': hashlib.sha256(query.encode()).hexdigest()[:16],
            'query_length': len(query),
            'parameter_count': len(parameters) if parameters else 0,
            'execution_time': execution_time,
            'security_issues': [],
            'performance_issues': [],
            'risk_level': 'low'
        }
        
        try:
            # Update statistics
            self.query_stats['total_queries'] += 1
            
            # Check query length
            if len(query) > self.config.max_query_length:
                audit_result['security_issues'].append('Query too long')
                audit_result['risk_level'] = 'medium'
            
            # Check for SQL injection patterns
            if self.config.enable_injection_detection:
                try:
                    self.query_builder.validate_query_string(query)
                except SQLInjectionError as e:
                    self.query_stats['injection_attempts'] += 1
                    audit_result['security_issues'].append(f'SQL injection detected: {str(e)}')
                    audit_result['risk_level'] = 'high'
                    
                    if self.config.alert_on_injection_attempts:
                        logger.error(
                            "SQL injection attempt detected",
                            query_hash=audit_result['query_hash'],
                            error=str(e),
                            connection_info=connection_info
                        )
            
            # Check for suspicious patterns
            if self.config.audit_raw_queries:
                for pattern in self.suspicious_patterns:
                    import re
                    if re.search(pattern, query, re.IGNORECASE):
                        audit_result['security_issues'].append(f'Suspicious pattern: {pattern}')
                        if audit_result['risk_level'] == 'low':
                            audit_result['risk_level'] = 'medium'
            
            # Check query complexity
            complexity_issues = self._check_query_complexity(query)
            if complexity_issues:
                audit_result['performance_issues'].extend(complexity_issues)
            
            # Check execution time
            if execution_time and execution_time > self.config.slow_query_threshold:
                self.query_stats['slow_queries'] += 1
                audit_result['performance_issues'].append('Slow query')
                
                if self.config.log_slow_queries:
                    logger.warning(
                        "Slow query detected",
                        query_hash=audit_result['query_hash'],
                        execution_time=execution_time,
                        threshold=self.config.slow_query_threshold
                    )
            
            # Log audit result
            if self.config.enable_query_auditing:
                if (audit_result['security_issues'] or 
                    audit_result['performance_issues'] or 
                    self.config.log_all_queries):
                    
                    logger.info(
                        "Database query audit",
                        **{k: v for k, v in audit_result.items() if k != 'timestamp'}
                    )
            
            return audit_result
            
        except Exception as e:
            logger.error("Query audit failed", error=str(e))
            audit_result['security_issues'].append(f'Audit failed: {str(e)}')
            return audit_result
    
    def _check_query_complexity(self, query: str) -> List[str]:
        """Check query complexity for performance issues"""
        issues = []
        query_lower = query.lower()
        
        # Count JOINs
        join_count = query_lower.count(' join ')
        if join_count > self.config.max_joins:
            issues.append(f'Too many JOINs: {join_count} (max: {self.config.max_joins})')
        
        # Count subqueries
        subquery_count = query_lower.count('select') - 1  # Subtract main SELECT
        if subquery_count > self.config.max_subqueries:
            issues.append(f'Too many subqueries: {subquery_count} (max: {self.config.max_subqueries})')
        
        # Check for Cartesian products (JOIN without ON clause)
        if ' join ' in query_lower and ' on ' not in query_lower:
            issues.append('Potential Cartesian product (JOIN without ON)')
        
        return issues
    
    def get_security_stats(self) -> Dict[str, Any]:
        """Get security monitoring statistics"""
        return {
            'query_stats': self.query_stats.copy(),
            'injection_rate': (
                self.query_stats['injection_attempts'] / max(1, self.query_stats['total_queries'])
            ),
            'slow_query_rate': (
                self.query_stats['slow_queries'] / max(1, self.query_stats['total_queries'])
            ),
            'config': {
                'injection_detection_enabled': self.config.enable_injection_detection,
                'query_auditing_enabled': self.config.enable_query_auditing,
                'slow_query_threshold': self.config.slow_query_threshold
            }
        }


# Global security monitor instance
security_monitor = DatabaseSecurityMonitor(DatabaseSecurityConfig())


def setup_database_security_events(engine: Engine) -> None:
    """
    Setup SQLAlchemy event listeners for database security
    
    Args:
        engine: SQLAlchemy engine instance
    """
    config = security_monitor.config
    
    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        """Log query execution start time"""
        context._query_start_time = time.time()
        
        # Log connection info for auditing
        context._connection_info = {
            'connection_id': id(conn),
            'database': conn.info.get('database', 'unknown'),
            'user': conn.info.get('user', 'unknown')
        }
    
    @event.listens_for(engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        """Audit completed query"""
        if not hasattr(context, '_query_start_time'):
            return
        
        execution_time = time.time() - context._query_start_time
        connection_info = getattr(context, '_connection_info', {})
        
        # Audit the query
        try:
            security_monitor.audit_query(
                query=statement,
                parameters=parameters,
                execution_time=execution_time,
                connection_info=connection_info
            )
        except Exception as e:
            logger.error("Failed to audit query", error=str(e))
    
    @event.listens_for(engine, "handle_error")
    def handle_error(exception_context):
        """Handle database errors"""
        security_monitor.query_stats['failed_queries'] += 1
        
        # Log security-relevant errors
        error_msg = str(exception_context.original_exception)
        if any(keyword in error_msg.lower() for keyword in ['injection', 'syntax', 'permission']):
            logger.error(
                "Database security error",
                error=error_msg,
                statement=exception_context.statement,
                connection_info=getattr(exception_context, '_connection_info', {})
            )
    
    if config.enable_connection_auditing:
        @event.listens_for(Pool, "connect")
        def on_connect(dbapi_conn, connection_record):
            """Audit new database connections"""
            logger.debug(
                "New database connection",
                connection_id=id(dbapi_conn),
                pool_size=connection_record.info.get('pool_size', 'unknown')
            )
        
        @event.listens_for(Pool, "checkout")
        def on_checkout(dbapi_conn, connection_record, connection_proxy):
            """Audit connection checkout"""
            connection_record.info['checkout_time'] = time.time()
        
        @event.listens_for(Pool, "checkin")
        def on_checkin(dbapi_conn, connection_record):
            """Audit connection checkin"""
            checkout_time = connection_record.info.get('checkout_time')
            if checkout_time:
                usage_time = time.time() - checkout_time
                if usage_time > config.max_connection_lifetime:
                    logger.warning(
                        "Long-lived database connection",
                        connection_id=id(dbapi_conn),
                        usage_time=usage_time,
                        max_lifetime=config.max_connection_lifetime
                    )
    
    logger.info("Database security event listeners configured")


def validate_orm_query(query: Any) -> bool:
    """
    Validate SQLAlchemy ORM query for security
    
    Args:
        query: SQLAlchemy query object
        
    Returns:
        bool: True if query is safe
    """
    try:
        # Convert query to string for validation
        query_str = str(query)
        
        # Use secure query builder for validation
        return security_monitor.query_builder.validate_query_string(query_str)
        
    except Exception as e:
        logger.error("ORM query validation failed", error=str(e))
        return False


def create_secure_text_query(
    query_template: str,
    parameters: Dict[str, Any]
) -> Any:
    """
    Create secure text query with validation
    
    Args:
        query_template: SQL query template
        parameters: Query parameters
        
    Returns:
        SQLAlchemy text query
    """
    return security_monitor.query_builder.create_safe_text_query(
        query_template, parameters
    )


def get_database_security_stats() -> Dict[str, Any]:
    """Get database security monitoring statistics"""
    return security_monitor.get_security_stats()


# Security middleware for database sessions
class DatabaseSecurityMiddleware:
    """Middleware for database session security"""
    
    def __init__(self, session: Session):
        self.session = session
        self.original_execute = session.execute
        self.original_query = session.query
        
        # Wrap session methods
        session.execute = self._secure_execute
        session.query = self._secure_query
    
    def _secure_execute(self, statement, parameters=None, **kwargs):
        """Secure wrapper for session.execute"""
        try:
            # Validate statement if it's a text query
            if hasattr(statement, 'text'):
                security_monitor.query_builder.validate_query_string(str(statement))
            
            return self.original_execute(statement, parameters, **kwargs)
            
        except SQLInjectionError as e:
            logger.error("SQL injection blocked in session.execute", error=str(e))
            raise
    
    def _secure_query(self, *args, **kwargs):
        """Secure wrapper for session.query"""
        query = self.original_query(*args, **kwargs)
        
        # Validate query when it's executed
        original_all = query.all
        original_first = query.first
        original_one = query.one
        
        def secure_all():
            validate_orm_query(query)
            return original_all()
        
        def secure_first():
            validate_orm_query(query)
            return original_first()
        
        def secure_one():
            validate_orm_query(query)
            return original_one()
        
        query.all = secure_all
        query.first = secure_first
        query.one = secure_one
        
        return query


# Export main classes and functions
__all__ = [
    'DatabaseSecurityConfig',
    'DatabaseSecurityMonitor',
    'DatabaseSecurityMiddleware',
    'setup_database_security_events',
    'validate_orm_query',
    'create_secure_text_query',
    'get_database_security_stats',
    'security_monitor'
]
