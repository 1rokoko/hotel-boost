"""
Tenant management utilities for multi-tenant architecture with Row Level Security
"""

import uuid
from typing import Optional, Dict, Any
from contextvars import ContextVar
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import logging

from app.core.logging import get_logger

logger = get_logger(__name__)

# Context variable to store current tenant ID for the request
current_tenant_id: ContextVar[Optional[uuid.UUID]] = ContextVar(
    'current_tenant_id', default=None
)

class TenantContext:
    """Manages tenant context for multi-tenant operations"""
    
    @staticmethod
    def set_tenant_id(tenant_id: uuid.UUID) -> None:
        """
        Set the current tenant ID in the context
        
        Args:
            tenant_id: UUID of the tenant
        """
        current_tenant_id.set(tenant_id)
        logger.debug(f"Tenant context set to: {tenant_id}")
    
    @staticmethod
    def get_tenant_id() -> Optional[uuid.UUID]:
        """
        Get the current tenant ID from context
        
        Returns:
            Optional[uuid.UUID]: Current tenant ID or None
        """
        return current_tenant_id.get()
    
    @staticmethod
    def clear_tenant_id() -> None:
        """Clear the current tenant ID from context"""
        current_tenant_id.set(None)
        logger.debug("Tenant context cleared")
    
    @staticmethod
    def require_tenant_id() -> uuid.UUID:
        """
        Get the current tenant ID, raising an error if not set
        
        Returns:
            uuid.UUID: Current tenant ID
            
        Raises:
            ValueError: If no tenant ID is set in context
        """
        tenant_id = current_tenant_id.get()
        if tenant_id is None:
            raise ValueError("No tenant ID set in context")
        return tenant_id

class TenantManager:
    """Manages tenant-specific database operations"""
    
    @staticmethod
    async def set_session_tenant(session: AsyncSession, tenant_id: uuid.UUID) -> None:
        """
        Set the tenant context for a database session
        
        Args:
            session: Database session
            tenant_id: UUID of the tenant
        """
        try:
            # Set the tenant context in PostgreSQL session
            await session.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)}
            )
            
            # Set the session role to tenant user
            await session.execute(text("SET SESSION ROLE hotel_bot_tenant"))
            
            logger.debug(f"Database session tenant context set to: {tenant_id}")
            
        except Exception as e:
            logger.error(f"Failed to set session tenant context: {str(e)}")
            raise
    
    @staticmethod
    async def clear_session_tenant(session: AsyncSession) -> None:
        """
        Clear the tenant context for a database session
        
        Args:
            session: Database session
        """
        try:
            # Reset the session role
            await session.execute(text("RESET ROLE"))
            
            # Clear the tenant context
            await session.execute(
                text("SELECT set_config('app.current_tenant_id', NULL, true)")
            )
            
            logger.debug("Database session tenant context cleared")
            
        except Exception as e:
            logger.error(f"Failed to clear session tenant context: {str(e)}")
            # Don't raise here as this is cleanup
    
    @staticmethod
    async def verify_tenant_access(
        session: AsyncSession, 
        tenant_id: uuid.UUID, 
        resource_tenant_id: uuid.UUID
    ) -> bool:
        """
        Verify that the current tenant has access to a resource
        
        Args:
            session: Database session
            tenant_id: Current tenant ID
            resource_tenant_id: Tenant ID of the resource being accessed
            
        Returns:
            bool: True if access is allowed, False otherwise
        """
        if tenant_id != resource_tenant_id:
            logger.warning(
                f"Tenant access denied: {tenant_id} attempted to access resource "
                f"belonging to {resource_tenant_id}"
            )
            return False
        return True
    
    @staticmethod
    async def log_tenant_action(
        session: AsyncSession,
        action: str,
        table_name: str,
        record_id: Optional[uuid.UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> None:
        """
        Log tenant action for audit purposes
        
        Args:
            session: Database session
            action: Action performed (CREATE, READ, UPDATE, DELETE)
            table_name: Name of the table affected
            record_id: ID of the record affected (optional)
            ip_address: IP address of the request (optional)
            user_agent: User agent of the request (optional)
        """
        try:
            tenant_id = TenantContext.get_tenant_id()
            if tenant_id:
                await session.execute(
                    text("""
                        SELECT log_tenant_action(
                            :tenant_id, :action, :table_name, :record_id, 
                            :ip_address, :user_agent
                        )
                    """),
                    {
                        "tenant_id": tenant_id,
                        "action": action,
                        "table_name": table_name,
                        "record_id": record_id,
                        "ip_address": ip_address,
                        "user_agent": user_agent
                    }
                )
                logger.debug(f"Logged tenant action: {action} on {table_name}")
        except Exception as e:
            logger.error(f"Failed to log tenant action: {str(e)}")
            # Don't raise here as logging failures shouldn't break the main operation

def get_tenant_filter(tenant_id: uuid.UUID) -> Dict[str, Any]:
    """
    Get filter dictionary for tenant-specific queries
    
    Args:
        tenant_id: UUID of the tenant
        
    Returns:
        Dict[str, Any]: Filter dictionary
    """
    return {"hotel_id": tenant_id}

def require_tenant_context() -> uuid.UUID:
    """
    Decorator helper to require tenant context
    
    Returns:
        uuid.UUID: Current tenant ID
        
    Raises:
        ValueError: If no tenant context is set
    """
    return TenantContext.require_tenant_id()
