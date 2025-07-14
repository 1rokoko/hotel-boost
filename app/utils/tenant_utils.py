"""
Tenant isolation utilities for WhatsApp Hotel Bot application
"""

import uuid
from typing import Dict, Any, List, Optional, Type, Union
from sqlalchemy.orm import Session, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import and_, or_, text, inspect
import structlog

from app.core.tenant_context import (
    HotelTenantContext,
    HotelTenantManager,
    get_current_hotel_id
)
from app.models.base import TenantBaseModel
from app.core.logging import get_logger

logger = get_logger(__name__)


class TenantIsolationError(Exception):
    """Exception raised when tenant isolation is violated"""
    pass


class TenantQueryBuilder:
    """Utility for building tenant-aware database queries"""
    
    @staticmethod
    def apply_tenant_filter(
        query: Query,
        model_class: Type[TenantBaseModel],
        hotel_id: Optional[uuid.UUID] = None
    ) -> Query:
        """
        Apply tenant filter to SQLAlchemy query
        
        Args:
            query: SQLAlchemy query object
            model_class: Model class that extends TenantBaseModel
            hotel_id: Optional hotel ID, uses current context if not provided
            
        Returns:
            Query: Filtered query object
            
        Raises:
            TenantIsolationError: If no hotel context is available
        """
        if hotel_id is None:
            hotel_id = get_current_hotel_id()
        
        if hotel_id is None:
            raise TenantIsolationError("No hotel ID provided and no hotel context set")
        
        # Verify model has hotel_id attribute
        if not hasattr(model_class, 'hotel_id'):
            raise TenantIsolationError(f"Model {model_class.__name__} does not support tenant isolation")
        
        return query.filter(model_class.hotel_id == hotel_id)
    
    @staticmethod
    def create_tenant_query(
        db: Session,
        model_class: Type[TenantBaseModel],
        hotel_id: Optional[uuid.UUID] = None
    ) -> Query:
        """
        Create a new tenant-filtered query
        
        Args:
            db: Database session
            model_class: Model class that extends TenantBaseModel
            hotel_id: Optional hotel ID, uses current context if not provided
            
        Returns:
            Query: Tenant-filtered query object
        """
        query = db.query(model_class)
        return TenantQueryBuilder.apply_tenant_filter(query, model_class, hotel_id)
    
    @staticmethod
    def get_tenant_count(
        db: Session,
        model_class: Type[TenantBaseModel],
        hotel_id: Optional[uuid.UUID] = None
    ) -> int:
        """
        Get count of records for tenant
        
        Args:
            db: Database session
            model_class: Model class that extends TenantBaseModel
            hotel_id: Optional hotel ID, uses current context if not provided
            
        Returns:
            int: Count of records
        """
        query = TenantQueryBuilder.create_tenant_query(db, model_class, hotel_id)
        return query.count()
    
    @staticmethod
    def verify_tenant_ownership(
        db: Session,
        model_instance: TenantBaseModel,
        hotel_id: Optional[uuid.UUID] = None
    ) -> bool:
        """
        Verify that a model instance belongs to the specified tenant
        
        Args:
            db: Database session
            model_instance: Model instance to verify
            hotel_id: Optional hotel ID, uses current context if not provided
            
        Returns:
            bool: True if instance belongs to tenant
        """
        if hotel_id is None:
            hotel_id = get_current_hotel_id()
        
        if hotel_id is None:
            raise TenantIsolationError("No hotel ID provided and no hotel context set")
        
        if not hasattr(model_instance, 'hotel_id'):
            raise TenantIsolationError(f"Model {type(model_instance).__name__} does not support tenant isolation")
        
        return model_instance.hotel_id == hotel_id


class TenantDataValidator:
    """Utility for validating tenant data isolation"""
    
    @staticmethod
    def validate_create_data(
        data: Dict[str, Any],
        model_class: Type[TenantBaseModel],
        hotel_id: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """
        Validate and ensure tenant isolation for create operations
        
        Args:
            data: Data dictionary for creating model instance
            model_class: Model class that extends TenantBaseModel
            hotel_id: Optional hotel ID, uses current context if not provided
            
        Returns:
            Dict[str, Any]: Validated data with hotel_id set
            
        Raises:
            TenantIsolationError: If tenant isolation would be violated
        """
        if hotel_id is None:
            hotel_id = get_current_hotel_id()
        
        if hotel_id is None:
            raise TenantIsolationError("No hotel ID provided and no hotel context set")
        
        # Ensure hotel_id is set correctly
        if 'hotel_id' in data:
            if data['hotel_id'] != hotel_id:
                raise TenantIsolationError(
                    f"Attempted to create {model_class.__name__} with different hotel_id "
                    f"(provided: {data['hotel_id']}, expected: {hotel_id})"
                )
        else:
            data = data.copy()
            data['hotel_id'] = hotel_id
        
        logger.debug(
            "Tenant data validated for create",
            model_class=model_class.__name__,
            hotel_id=str(hotel_id)
        )
        
        return data
    
    @staticmethod
    def validate_update_data(
        data: Dict[str, Any],
        model_instance: TenantBaseModel,
        hotel_id: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """
        Validate and ensure tenant isolation for update operations
        
        Args:
            data: Data dictionary for updating model instance
            model_instance: Existing model instance
            hotel_id: Optional hotel ID, uses current context if not provided
            
        Returns:
            Dict[str, Any]: Validated data
            
        Raises:
            TenantIsolationError: If tenant isolation would be violated
        """
        if hotel_id is None:
            hotel_id = get_current_hotel_id()
        
        if hotel_id is None:
            raise TenantIsolationError("No hotel ID provided and no hotel context set")
        
        # Verify ownership of existing instance
        if not TenantQueryBuilder.verify_tenant_ownership(None, model_instance, hotel_id):
            raise TenantIsolationError(
                f"Attempted to update {type(model_instance).__name__} belonging to different hotel"
            )
        
        # Prevent hotel_id changes
        if 'hotel_id' in data:
            if data['hotel_id'] != hotel_id:
                raise TenantIsolationError(
                    f"Attempted to change hotel_id in update operation "
                    f"(from: {model_instance.hotel_id}, to: {data['hotel_id']})"
                )
            # Remove hotel_id from update data to prevent unnecessary updates
            data = data.copy()
            del data['hotel_id']
        
        logger.debug(
            "Tenant data validated for update",
            model_class=type(model_instance).__name__,
            hotel_id=str(hotel_id),
            instance_id=str(getattr(model_instance, 'id', 'unknown'))
        )
        
        return data


class TenantBulkOperations:
    """Utility for tenant-aware bulk operations"""
    
    @staticmethod
    def bulk_create(
        db: Session,
        model_class: Type[TenantBaseModel],
        data_list: List[Dict[str, Any]],
        hotel_id: Optional[uuid.UUID] = None
    ) -> List[TenantBaseModel]:
        """
        Bulk create records with tenant isolation
        
        Args:
            db: Database session
            model_class: Model class that extends TenantBaseModel
            data_list: List of data dictionaries
            hotel_id: Optional hotel ID, uses current context if not provided
            
        Returns:
            List[TenantBaseModel]: Created instances
        """
        if hotel_id is None:
            hotel_id = get_current_hotel_id()
        
        if hotel_id is None:
            raise TenantIsolationError("No hotel ID provided and no hotel context set")
        
        # Validate all data
        validated_data = []
        for data in data_list:
            validated = TenantDataValidator.validate_create_data(data, model_class, hotel_id)
            validated_data.append(validated)
        
        # Create instances
        instances = []
        for data in validated_data:
            instance = model_class(**data)
            db.add(instance)
            instances.append(instance)
        
        logger.info(
            "Bulk create operation completed",
            model_class=model_class.__name__,
            count=len(instances),
            hotel_id=str(hotel_id)
        )
        
        return instances
    
    @staticmethod
    def bulk_update(
        db: Session,
        model_class: Type[TenantBaseModel],
        updates: Dict[Any, Dict[str, Any]],
        hotel_id: Optional[uuid.UUID] = None
    ) -> int:
        """
        Bulk update records with tenant isolation
        
        Args:
            db: Database session
            model_class: Model class that extends TenantBaseModel
            updates: Dictionary mapping instance IDs to update data
            hotel_id: Optional hotel ID, uses current context if not provided
            
        Returns:
            int: Number of updated records
        """
        if hotel_id is None:
            hotel_id = get_current_hotel_id()
        
        if hotel_id is None:
            raise TenantIsolationError("No hotel ID provided and no hotel context set")
        
        # Get all instances to update
        instance_ids = list(updates.keys())
        query = TenantQueryBuilder.create_tenant_query(db, model_class, hotel_id)
        instances = query.filter(model_class.id.in_(instance_ids)).all()
        
        # Verify all instances belong to tenant
        found_ids = {instance.id for instance in instances}
        missing_ids = set(instance_ids) - found_ids
        
        if missing_ids:
            raise TenantIsolationError(
                f"Some {model_class.__name__} instances not found or don't belong to hotel: {missing_ids}"
            )
        
        # Apply updates
        updated_count = 0
        for instance in instances:
            update_data = updates.get(instance.id, {})
            if update_data:
                validated_data = TenantDataValidator.validate_update_data(
                    update_data, instance, hotel_id
                )
                
                for key, value in validated_data.items():
                    setattr(instance, key, value)
                
                updated_count += 1
        
        logger.info(
            "Bulk update operation completed",
            model_class=model_class.__name__,
            updated_count=updated_count,
            hotel_id=str(hotel_id)
        )
        
        return updated_count
    
    @staticmethod
    def bulk_delete(
        db: Session,
        model_class: Type[TenantBaseModel],
        instance_ids: List[Any],
        hotel_id: Optional[uuid.UUID] = None
    ) -> int:
        """
        Bulk delete records with tenant isolation
        
        Args:
            db: Database session
            model_class: Model class that extends TenantBaseModel
            instance_ids: List of instance IDs to delete
            hotel_id: Optional hotel ID, uses current context if not provided
            
        Returns:
            int: Number of deleted records
        """
        if hotel_id is None:
            hotel_id = get_current_hotel_id()
        
        if hotel_id is None:
            raise TenantIsolationError("No hotel ID provided and no hotel context set")
        
        # Delete with tenant filter
        query = TenantQueryBuilder.create_tenant_query(db, model_class, hotel_id)
        deleted_count = query.filter(model_class.id.in_(instance_ids)).delete(synchronize_session=False)
        
        logger.info(
            "Bulk delete operation completed",
            model_class=model_class.__name__,
            deleted_count=deleted_count,
            hotel_id=str(hotel_id)
        )
        
        return deleted_count


class TenantDataMigration:
    """Utility for tenant data migration operations"""
    
    @staticmethod
    def export_tenant_data(
        db: Session,
        model_classes: List[Type[TenantBaseModel]],
        hotel_id: Optional[uuid.UUID] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Export all data for a tenant
        
        Args:
            db: Database session
            model_classes: List of model classes to export
            hotel_id: Optional hotel ID, uses current context if not provided
            
        Returns:
            Dict[str, List[Dict[str, Any]]]: Exported data by model class name
        """
        if hotel_id is None:
            hotel_id = get_current_hotel_id()
        
        if hotel_id is None:
            raise TenantIsolationError("No hotel ID provided and no hotel context set")
        
        exported_data = {}
        
        for model_class in model_classes:
            query = TenantQueryBuilder.create_tenant_query(db, model_class, hotel_id)
            instances = query.all()
            
            # Convert instances to dictionaries
            model_data = []
            for instance in instances:
                instance_dict = {}
                for column in inspect(model_class).columns:
                    value = getattr(instance, column.name)
                    # Convert UUID and datetime objects to strings
                    if isinstance(value, uuid.UUID):
                        value = str(value)
                    elif hasattr(value, 'isoformat'):
                        value = value.isoformat()
                    instance_dict[column.name] = value
                
                model_data.append(instance_dict)
            
            exported_data[model_class.__name__] = model_data
            
            logger.debug(
                "Model data exported",
                model_class=model_class.__name__,
                count=len(model_data),
                hotel_id=str(hotel_id)
            )
        
        logger.info(
            "Tenant data export completed",
            hotel_id=str(hotel_id),
            model_count=len(model_classes),
            total_records=sum(len(data) for data in exported_data.values())
        )
        
        return exported_data
    
    @staticmethod
    def import_tenant_data(
        db: Session,
        data: Dict[str, List[Dict[str, Any]]],
        model_classes: Dict[str, Type[TenantBaseModel]],
        hotel_id: Optional[uuid.UUID] = None,
        replace_existing: bool = False
    ) -> Dict[str, int]:
        """
        Import data for a tenant
        
        Args:
            db: Database session
            data: Data to import by model class name
            model_classes: Map of model class names to model classes
            hotel_id: Optional hotel ID, uses current context if not provided
            replace_existing: Whether to replace existing data
            
        Returns:
            Dict[str, int]: Count of imported records by model class name
        """
        if hotel_id is None:
            hotel_id = get_current_hotel_id()
        
        if hotel_id is None:
            raise TenantIsolationError("No hotel ID provided and no hotel context set")
        
        imported_counts = {}
        
        # Clear existing data if replace_existing is True
        if replace_existing:
            for model_name, model_class in model_classes.items():
                if model_name in data:
                    query = TenantQueryBuilder.create_tenant_query(db, model_class, hotel_id)
                    deleted_count = query.delete(synchronize_session=False)
                    logger.info(
                        "Existing data cleared for import",
                        model_class=model_name,
                        deleted_count=deleted_count,
                        hotel_id=str(hotel_id)
                    )
        
        # Import data
        for model_name, model_data in data.items():
            if model_name not in model_classes:
                logger.warning(
                    "Model class not found for import",
                    model_name=model_name,
                    hotel_id=str(hotel_id)
                )
                continue
            
            model_class = model_classes[model_name]
            
            # Validate and create instances
            instances = TenantBulkOperations.bulk_create(
                db, model_class, model_data, hotel_id
            )
            
            imported_counts[model_name] = len(instances)
            
            logger.debug(
                "Model data imported",
                model_class=model_name,
                count=len(instances),
                hotel_id=str(hotel_id)
            )
        
        logger.info(
            "Tenant data import completed",
            hotel_id=str(hotel_id),
            imported_counts=imported_counts
        )
        
        return imported_counts


# Convenience functions
def ensure_tenant_isolation(func):
    """
    Decorator to ensure tenant isolation for database operations
    
    Args:
        func: Function to decorate
        
    Returns:
        Decorated function
    """
    def wrapper(*args, **kwargs):
        hotel_id = get_current_hotel_id()
        if hotel_id is None:
            raise TenantIsolationError("No hotel context set for tenant isolation")
        return func(*args, **kwargs)
    
    return wrapper


def get_tenant_query(
    db: Session,
    model_class: Type[TenantBaseModel],
    hotel_id: Optional[uuid.UUID] = None
) -> Query:
    """
    Get tenant-filtered query (convenience function)
    
    Args:
        db: Database session
        model_class: Model class that extends TenantBaseModel
        hotel_id: Optional hotel ID, uses current context if not provided
        
    Returns:
        Query: Tenant-filtered query object
    """
    return TenantQueryBuilder.create_tenant_query(db, model_class, hotel_id)


def validate_tenant_data(
    data: Dict[str, Any],
    model_class: Type[TenantBaseModel],
    hotel_id: Optional[uuid.UUID] = None
) -> Dict[str, Any]:
    """
    Validate tenant data (convenience function)
    
    Args:
        data: Data dictionary
        model_class: Model class that extends TenantBaseModel
        hotel_id: Optional hotel ID, uses current context if not provided
        
    Returns:
        Dict[str, Any]: Validated data
    """
    return TenantDataValidator.validate_create_data(data, model_class, hotel_id)
