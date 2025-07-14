"""
Base model classes for the WhatsApp Hotel Bot application
"""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy import Column, DateTime, String, Boolean, text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

# Create the declarative base
Base = declarative_base()

class TimestampMixin:
    """Mixin for adding timestamp fields to models"""
    
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Timestamp when the record was created"
    )
    
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Timestamp when the record was last updated"
    )

class UUIDMixin:
    """Mixin for adding UUID primary key to models"""
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
        comment="Unique identifier for the record"
    )

class SoftDeleteMixin:
    """Mixin for adding soft delete functionality to models"""
    
    is_deleted = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Indicates if the record is soft deleted"
    )
    
    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when the record was soft deleted"
    )

class BaseModel(Base, UUIDMixin, TimestampMixin):
    """
    Base model class with UUID primary key and timestamps
    
    All models should inherit from this class to ensure consistency
    """
    __abstract__ = True
    
    def __repr__(self) -> str:
        """String representation of the model"""
        return f"<{self.__class__.__name__}(id={self.id})>"
    
    def to_dict(self, exclude_fields: Optional[set] = None) -> Dict[str, Any]:
        """
        Convert model instance to dictionary
        
        Args:
            exclude_fields: Set of field names to exclude from the dictionary
            
        Returns:
            Dict[str, Any]: Dictionary representation of the model
        """
        exclude_fields = exclude_fields or set()
        result = {}
        
        for column in self.__table__.columns:
            if column.name not in exclude_fields:
                value = getattr(self, column.name)
                # Convert datetime objects to ISO format strings
                if isinstance(value, datetime):
                    value = value.isoformat()
                # Convert UUID objects to strings
                elif isinstance(value, uuid.UUID):
                    value = str(value)
                result[column.name] = value
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BaseModel":
        """
        Create model instance from dictionary
        
        Args:
            data: Dictionary with model data
            
        Returns:
            BaseModel: New model instance
        """
        # Filter out any keys that don't correspond to model columns
        valid_columns = {column.name for column in cls.__table__.columns}
        filtered_data = {k: v for k, v in data.items() if k in valid_columns}
        
        return cls(**filtered_data)
    
    def update_from_dict(self, data: Dict[str, Any], exclude_fields: Optional[set] = None) -> None:
        """
        Update model instance from dictionary
        
        Args:
            data: Dictionary with updated data
            exclude_fields: Set of field names to exclude from update
        """
        exclude_fields = exclude_fields or {'id', 'created_at'}
        valid_columns = {column.name for column in self.__table__.columns}
        
        for key, value in data.items():
            if key in valid_columns and key not in exclude_fields:
                setattr(self, key, value)

class TenantBaseModel(BaseModel):
    """
    Base model for tenant-specific data with hotel_id foreign key
    
    This model includes the hotel_id field for multi-tenant data isolation
    """
    __abstract__ = True
    
    @declared_attr
    def hotel_id(cls):
        """Hotel ID for multi-tenant data isolation"""
        return Column(
            UUID(as_uuid=True),
            ForeignKey('hotels.id', ondelete='CASCADE'),
            nullable=False,
            comment="Hotel ID for multi-tenant data isolation"
        )
    
    def __repr__(self) -> str:
        """String representation including hotel_id"""
        return f"<{self.__class__.__name__}(id={self.id}, hotel_id={self.hotel_id})>"

class AuditableModel(BaseModel, SoftDeleteMixin):
    """
    Base model with audit trail capabilities including soft delete
    
    This model includes soft delete functionality and audit fields
    """
    __abstract__ = True
    
    created_by = Column(
        String(255),
        nullable=True,
        comment="User who created the record"
    )
    
    updated_by = Column(
        String(255),
        nullable=True,
        comment="User who last updated the record"
    )
    
    version = Column(
        String(50),
        nullable=True,
        comment="Version of the record for optimistic locking"
    )
    
    def soft_delete(self, deleted_by: Optional[str] = None) -> None:
        """
        Perform soft delete on the record
        
        Args:
            deleted_by: User performing the deletion
        """
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()
        if deleted_by:
            self.updated_by = deleted_by
    
    def restore(self, restored_by: Optional[str] = None) -> None:
        """
        Restore a soft-deleted record
        
        Args:
            restored_by: User performing the restoration
        """
        self.is_deleted = False
        self.deleted_at = None
        if restored_by:
            self.updated_by = restored_by

class TenantAuditableModel(TenantBaseModel, SoftDeleteMixin):
    """
    Base model for tenant-specific data with audit capabilities
    
    Combines tenant isolation with audit trail functionality
    """
    __abstract__ = True
    
    created_by = Column(
        String(255),
        nullable=True,
        comment="User who created the record"
    )
    
    updated_by = Column(
        String(255),
        nullable=True,
        comment="User who last updated the record"
    )
    
    def soft_delete(self, deleted_by: Optional[str] = None) -> None:
        """
        Perform soft delete on the record
        
        Args:
            deleted_by: User performing the deletion
        """
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()
        if deleted_by:
            self.updated_by = deleted_by
    
    def restore(self, restored_by: Optional[str] = None) -> None:
        """
        Restore a soft-deleted record
        
        Args:
            restored_by: User performing the restoration
        """
        self.is_deleted = False
        self.deleted_at = None
        if restored_by:
            self.updated_by = restored_by

# Export all base classes
__all__ = [
    'Base',
    'BaseModel',
    'TenantBaseModel', 
    'AuditableModel',
    'TenantAuditableModel',
    'TimestampMixin',
    'UUIDMixin',
    'SoftDeleteMixin'
]
