"""
Database logging system with structured JSON output
"""

import time
import uuid
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
import logging

from app.core.logging import get_logger
from app.core.tenant import TenantContext

logger = get_logger(__name__)

class DatabaseLogger:
    """
    Structured database operation logger
    
    Logs all database operations with detailed metadata in JSON format
    """
    
    def __init__(self):
        self.query_count = 0
        self.slow_query_threshold = 1000  # milliseconds
        self.log_all_queries = False
        self.log_slow_queries = True
        self.log_errors = True
        
    def configure(
        self,
        log_all_queries: bool = False,
        log_slow_queries: bool = True,
        log_errors: bool = True,
        slow_query_threshold: int = 1000
    ) -> None:
        """
        Configure database logging settings
        
        Args:
            log_all_queries: Whether to log all queries
            log_slow_queries: Whether to log slow queries
            log_errors: Whether to log database errors
            slow_query_threshold: Threshold in milliseconds for slow queries
        """
        self.log_all_queries = log_all_queries
        self.log_slow_queries = log_slow_queries
        self.log_errors = log_errors
        self.slow_query_threshold = slow_query_threshold
    
    def log_query_start(
        self,
        query_id: str,
        statement: str,
        parameters: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[uuid.UUID] = None,
        correlation_id: Optional[str] = None
    ) -> None:
        """
        Log query start
        
        Args:
            query_id: Unique query identifier
            statement: SQL statement
            parameters: Query parameters
            tenant_id: Current tenant ID
            correlation_id: Request correlation ID
        """
        if self.log_all_queries:
            log_data = {
                "event": "database_query_start",
                "query_id": query_id,
                "statement": self._sanitize_statement(statement),
                "parameter_count": len(parameters) if parameters else 0,
                "tenant_id": str(tenant_id) if tenant_id else None,
                "correlation_id": correlation_id,
                "timestamp": datetime.utcnow().isoformat()
            }
            logger.debug("Database query started", extra=log_data)
    
    def log_query_end(
        self,
        query_id: str,
        statement: str,
        parameters: Optional[Dict[str, Any]] = None,
        execution_time_ms: float = 0,
        rows_affected: Optional[int] = None,
        tenant_id: Optional[uuid.UUID] = None,
        correlation_id: Optional[str] = None,
        error: Optional[str] = None
    ) -> None:
        """
        Log query completion
        
        Args:
            query_id: Unique query identifier
            statement: SQL statement
            parameters: Query parameters
            execution_time_ms: Query execution time in milliseconds
            rows_affected: Number of rows affected
            tenant_id: Current tenant ID
            correlation_id: Request correlation ID
            error: Error message if query failed
        """
        self.query_count += 1
        
        log_data = {
            "event": "database_query_end",
            "query_id": query_id,
            "statement": self._sanitize_statement(statement),
            "execution_time_ms": round(execution_time_ms, 2),
            "rows_affected": rows_affected,
            "parameter_count": len(parameters) if parameters else 0,
            "tenant_id": str(tenant_id) if tenant_id else None,
            "correlation_id": correlation_id,
            "timestamp": datetime.utcnow().isoformat(),
            "total_queries": self.query_count
        }
        
        # Determine log level and whether to log
        should_log = False
        log_level = "debug"
        
        if error:
            should_log = self.log_errors
            log_level = "error"
            log_data["error"] = error
            log_data["event"] = "database_query_error"
        elif execution_time_ms > self.slow_query_threshold:
            should_log = self.log_slow_queries
            log_level = "warning"
            log_data["event"] = "database_slow_query"
        elif self.log_all_queries:
            should_log = True
            log_level = "debug"
        
        if should_log:
            getattr(logger, log_level)("Database query completed", extra=log_data)
    
    def log_connection_event(
        self,
        event_type: str,
        connection_id: str,
        pool_stats: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> None:
        """
        Log database connection events
        
        Args:
            event_type: Type of connection event
            connection_id: Connection identifier
            pool_stats: Connection pool statistics
            error: Error message if applicable
        """
        log_data = {
            "event": f"database_connection_{event_type}",
            "connection_id": connection_id,
            "pool_stats": pool_stats,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if error:
            log_data["error"] = error
            logger.error(f"Database connection {event_type} failed", extra=log_data)
        else:
            logger.debug(f"Database connection {event_type}", extra=log_data)
    
    def log_transaction_event(
        self,
        event_type: str,
        transaction_id: str,
        tenant_id: Optional[uuid.UUID] = None,
        correlation_id: Optional[str] = None,
        duration_ms: Optional[float] = None,
        error: Optional[str] = None
    ) -> None:
        """
        Log database transaction events
        
        Args:
            event_type: Type of transaction event (begin, commit, rollback)
            transaction_id: Transaction identifier
            tenant_id: Current tenant ID
            correlation_id: Request correlation ID
            duration_ms: Transaction duration in milliseconds
            error: Error message if applicable
        """
        log_data = {
            "event": f"database_transaction_{event_type}",
            "transaction_id": transaction_id,
            "tenant_id": str(tenant_id) if tenant_id else None,
            "correlation_id": correlation_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if duration_ms is not None:
            log_data["duration_ms"] = round(duration_ms, 2)
        
        if error:
            log_data["error"] = error
            logger.error(f"Database transaction {event_type} failed", extra=log_data)
        else:
            logger.info(f"Database transaction {event_type}", extra=log_data)
    
    def _sanitize_statement(self, statement: str) -> str:
        """
        Sanitize SQL statement for logging
        
        Args:
            statement: SQL statement
            
        Returns:
            str: Sanitized statement
        """
        # Remove extra whitespace and limit length
        sanitized = " ".join(statement.split())
        if len(sanitized) > 500:
            sanitized = sanitized[:497] + "..."
        return sanitized
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get database logging statistics
        
        Returns:
            Dict[str, Any]: Logging statistics
        """
        return {
            "total_queries": self.query_count,
            "log_all_queries": self.log_all_queries,
            "log_slow_queries": self.log_slow_queries,
            "log_errors": self.log_errors,
            "slow_query_threshold_ms": self.slow_query_threshold
        }

# Global database logger instance
db_logger = DatabaseLogger()

class DatabaseSessionLogger:
    """
    Context manager for logging database session operations
    """
    
    def __init__(
        self,
        session: AsyncSession,
        operation: str,
        correlation_id: Optional[str] = None
    ):
        self.session = session
        self.operation = operation
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.start_time = None
        self.tenant_id = None
    
    async def __aenter__(self):
        self.start_time = time.time()
        self.tenant_id = TenantContext.get_tenant_id()
        
        db_logger.log_transaction_event(
            "begin",
            self.correlation_id,
            self.tenant_id,
            self.correlation_id
        )
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.time() - self.start_time) * 1000 if self.start_time else 0
        
        if exc_type:
            db_logger.log_transaction_event(
                "rollback",
                self.correlation_id,
                self.tenant_id,
                self.correlation_id,
                duration_ms,
                str(exc_val)
            )
        else:
            db_logger.log_transaction_event(
                "commit",
                self.correlation_id,
                self.tenant_id,
                self.correlation_id,
                duration_ms
            )

@asynccontextmanager
async def logged_db_session(session: AsyncSession, operation: str):
    """
    Context manager for logged database sessions
    
    Args:
        session: Database session
        operation: Operation description
        
    Yields:
        DatabaseSessionLogger: Session logger
    """
    async with DatabaseSessionLogger(session, operation) as session_logger:
        yield session_logger

def setup_database_logging(engine: Engine, debug: bool = False) -> None:
    """
    Set up database event listeners for logging
    
    Args:
        engine: SQLAlchemy engine
        debug: Whether to enable debug logging
    """
    # Configure logger based on debug mode
    db_logger.configure(
        log_all_queries=debug,
        log_slow_queries=True,
        log_errors=True,
        slow_query_threshold=1000 if not debug else 100
    )
    
    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        """Log query start"""
        query_id = str(uuid.uuid4())
        context._query_id = query_id
        context._query_start_time = time.time()
        
        tenant_id = TenantContext.get_tenant_id()
        correlation_id = getattr(context, 'correlation_id', None)
        
        db_logger.log_query_start(
            query_id,
            statement,
            parameters,
            tenant_id,
            correlation_id
        )
    
    @event.listens_for(engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        """Log query completion"""
        query_id = getattr(context, '_query_id', 'unknown')
        start_time = getattr(context, '_query_start_time', time.time())
        execution_time_ms = (time.time() - start_time) * 1000
        
        tenant_id = TenantContext.get_tenant_id()
        correlation_id = getattr(context, 'correlation_id', None)
        rows_affected = cursor.rowcount if hasattr(cursor, 'rowcount') else None
        
        db_logger.log_query_end(
            query_id,
            statement,
            parameters,
            execution_time_ms,
            rows_affected,
            tenant_id,
            correlation_id
        )
    
    # Only add dbapi_error listener for databases that support it
    if not engine.url.drivername.startswith('sqlite'):
        @event.listens_for(engine, "dbapi_error")
        def dbapi_error(conn, cursor, statement, parameters, context, exception):
            """Log database errors"""
            query_id = getattr(context, '_query_id', 'unknown')
            start_time = getattr(context, '_query_start_time', time.time())
            execution_time_ms = (time.time() - start_time) * 1000

            tenant_id = TenantContext.get_tenant_id()
            correlation_id = getattr(context, 'correlation_id', None)

            db_logger.log_query_end(
                query_id,
                statement,
                parameters,
                execution_time_ms,
                None,
                tenant_id,
                correlation_id,
                str(exception)
            )
