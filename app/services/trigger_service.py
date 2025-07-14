"""
Trigger service for WhatsApp Hotel Bot application
"""

import uuid
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import and_, or_, func, desc, asc
import structlog

from app.models.trigger import Trigger, TriggerType
from app.models.hotel import Hotel
from app.schemas.trigger import (
    TriggerCreate,
    TriggerUpdate,
    TriggerResponse,
    TriggerListResponse,
    TriggerTestData,
    TriggerTestResult
)
from app.schemas.trigger_config import (
    TriggerTemplateValidation,
    TriggerStatistics,
    TriggerPerformanceMetrics
)
from app.core.tenant import TenantContext, require_tenant_context
from app.core.logging import get_logger
from app.logging.trigger_logger import get_trigger_logger, TriggerEventType
from app.monitoring.trigger_metrics import trigger_metrics

logger = get_logger(__name__)


class TriggerServiceError(Exception):
    """Base exception for trigger service errors"""
    pass


class TriggerNotFoundError(TriggerServiceError):
    """Raised when trigger is not found"""
    pass


class TriggerValidationError(TriggerServiceError):
    """Raised when trigger validation fails"""
    pass


class TriggerTemplateError(TriggerServiceError):
    """Raised when trigger template is invalid"""
    pass


class TriggerService:
    """Service for managing trigger operations"""
    
    def __init__(self, db: Session):
        """
        Initialize trigger service

        Args:
            db: Database session
        """
        self.db = db
        self.logger = logger.bind(service="trigger_service")
        self.trigger_logger = get_trigger_logger()
    
    def create_trigger(self, hotel_id: uuid.UUID, trigger_data: TriggerCreate) -> TriggerResponse:
        """
        Create a new trigger
        
        Args:
            hotel_id: Hotel ID for tenant isolation
            trigger_data: Trigger creation data
            
        Returns:
            TriggerResponse: Created trigger data
            
        Raises:
            TriggerValidationError: If trigger validation fails
            TriggerServiceError: If creation fails
        """
        try:
            # Verify hotel exists
            hotel = self.db.query(Hotel).filter(Hotel.id == hotel_id).first()
            if not hotel:
                raise TriggerServiceError(f"Hotel with ID {hotel_id} not found")
            
            # Validate trigger template
            template_validation = self._validate_template(trigger_data.message_template)
            if not template_validation.is_valid:
                raise TriggerTemplateError(
                    f"Invalid template: {', '.join(template_validation.errors)}"
                )
            
            # Convert conditions to dict format for storage
            conditions_dict = self._convert_conditions_to_dict(trigger_data.conditions)
            
            # Create trigger instance
            trigger = Trigger(
                hotel_id=hotel_id,
                name=trigger_data.name,
                trigger_type=trigger_data.trigger_type,
                conditions=conditions_dict,
                message_template=trigger_data.message_template,
                is_active=trigger_data.is_active,
                priority=trigger_data.priority
            )
            
            # Add to database
            self.db.add(trigger)
            self.db.commit()
            self.db.refresh(trigger)
            
            self.logger.info(
                "Trigger created successfully",
                trigger_id=str(trigger.id),
                hotel_id=str(hotel_id),
                trigger_name=trigger.name,
                trigger_type=trigger.trigger_type.value
            )
            
            return TriggerResponse.from_orm(trigger)
            
        except (TriggerValidationError, TriggerTemplateError):
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            self.logger.error(
                "Database error creating trigger",
                hotel_id=str(hotel_id),
                error=str(e)
            )
            raise TriggerServiceError(f"Failed to create trigger: {str(e)}")
        except Exception as e:
            self.db.rollback()
            self.logger.error(
                "Unexpected error creating trigger",
                hotel_id=str(hotel_id),
                error=str(e)
            )
            raise TriggerServiceError(f"Unexpected error: {str(e)}")
    
    def get_trigger(self, hotel_id: uuid.UUID, trigger_id: uuid.UUID) -> TriggerResponse:
        """
        Get trigger by ID
        
        Args:
            hotel_id: Hotel ID for tenant isolation
            trigger_id: Trigger ID
            
        Returns:
            TriggerResponse: Trigger data
            
        Raises:
            TriggerNotFoundError: If trigger is not found
        """
        try:
            trigger = self.db.query(Trigger).filter(
                and_(
                    Trigger.id == trigger_id,
                    Trigger.hotel_id == hotel_id
                )
            ).first()
            
            if not trigger:
                raise TriggerNotFoundError(f"Trigger with ID {trigger_id} not found")
            
            return TriggerResponse.from_orm(trigger)
            
        except TriggerNotFoundError:
            raise
        except Exception as e:
            self.logger.error(
                "Error retrieving trigger",
                hotel_id=str(hotel_id),
                trigger_id=str(trigger_id),
                error=str(e)
            )
            raise TriggerServiceError(f"Failed to retrieve trigger: {str(e)}")
    
    def update_trigger(
        self,
        hotel_id: uuid.UUID,
        trigger_id: uuid.UUID,
        trigger_data: TriggerUpdate
    ) -> TriggerResponse:
        """
        Update trigger
        
        Args:
            hotel_id: Hotel ID for tenant isolation
            trigger_id: Trigger ID
            trigger_data: Trigger update data
            
        Returns:
            TriggerResponse: Updated trigger data
            
        Raises:
            TriggerNotFoundError: If trigger is not found
            TriggerValidationError: If validation fails
        """
        try:
            trigger = self.db.query(Trigger).filter(
                and_(
                    Trigger.id == trigger_id,
                    Trigger.hotel_id == hotel_id
                )
            ).first()
            
            if not trigger:
                raise TriggerNotFoundError(f"Trigger with ID {trigger_id} not found")
            
            # Update fields if provided
            if trigger_data.name is not None:
                trigger.name = trigger_data.name
            
            if trigger_data.message_template is not None:
                # Validate new template
                template_validation = self._validate_template(trigger_data.message_template)
                if not template_validation.is_valid:
                    raise TriggerTemplateError(
                        f"Invalid template: {', '.join(template_validation.errors)}"
                    )
                trigger.message_template = trigger_data.message_template
            
            if trigger_data.conditions is not None:
                conditions_dict = self._convert_conditions_to_dict(trigger_data.conditions)
                trigger.conditions = conditions_dict
            
            if trigger_data.is_active is not None:
                trigger.is_active = trigger_data.is_active
            
            if trigger_data.priority is not None:
                trigger.priority = trigger_data.priority
            
            # Update timestamp
            trigger.updated_at = datetime.utcnow()
            
            self.db.commit()
            self.db.refresh(trigger)
            
            self.logger.info(
                "Trigger updated successfully",
                trigger_id=str(trigger_id),
                hotel_id=str(hotel_id)
            )
            
            return TriggerResponse.from_orm(trigger)
            
        except (TriggerNotFoundError, TriggerValidationError, TriggerTemplateError):
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            self.logger.error(
                "Database error updating trigger",
                hotel_id=str(hotel_id),
                trigger_id=str(trigger_id),
                error=str(e)
            )
            raise TriggerServiceError(f"Failed to update trigger: {str(e)}")
    
    def delete_trigger(self, hotel_id: uuid.UUID, trigger_id: uuid.UUID) -> bool:
        """
        Delete trigger
        
        Args:
            hotel_id: Hotel ID for tenant isolation
            trigger_id: Trigger ID
            
        Returns:
            bool: True if deleted successfully
            
        Raises:
            TriggerNotFoundError: If trigger is not found
        """
        try:
            trigger = self.db.query(Trigger).filter(
                and_(
                    Trigger.id == trigger_id,
                    Trigger.hotel_id == hotel_id
                )
            ).first()
            
            if not trigger:
                raise TriggerNotFoundError(f"Trigger with ID {trigger_id} not found")
            
            self.db.delete(trigger)
            self.db.commit()
            
            self.logger.info(
                "Trigger deleted successfully",
                trigger_id=str(trigger_id),
                hotel_id=str(hotel_id)
            )
            
            return True
            
        except TriggerNotFoundError:
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            self.logger.error(
                "Database error deleting trigger",
                hotel_id=str(hotel_id),
                trigger_id=str(trigger_id),
                error=str(e)
            )
            raise TriggerServiceError(f"Failed to delete trigger: {str(e)}")
    
    def _validate_template(self, template: str) -> TriggerTemplateValidation:
        """
        Validate trigger template
        
        Args:
            template: Template string to validate
            
        Returns:
            TriggerTemplateValidation: Validation result
        """
        # This will be implemented with Jinja2 validation in the next task
        # For now, return basic validation
        return TriggerTemplateValidation(
            is_valid=True,
            variables=[],
            errors=[],
            warnings=[]
        )
    
    def list_triggers(
        self,
        hotel_id: uuid.UUID,
        page: int = 1,
        size: int = 20,
        trigger_type: Optional[TriggerType] = None,
        is_active: Optional[bool] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> TriggerListResponse:
        """
        List triggers with pagination and filtering

        Args:
            hotel_id: Hotel ID for tenant isolation
            page: Page number (1-based)
            size: Page size
            trigger_type: Filter by trigger type
            is_active: Filter by active status
            sort_by: Sort field
            sort_order: Sort order (asc/desc)

        Returns:
            TriggerListResponse: Paginated trigger list
        """
        try:
            # Build query with filters
            query = self.db.query(Trigger).filter(Trigger.hotel_id == hotel_id)

            if trigger_type is not None:
                query = query.filter(Trigger.trigger_type == trigger_type)

            if is_active is not None:
                query = query.filter(Trigger.is_active == is_active)

            # Apply sorting
            sort_column = getattr(Trigger, sort_by, Trigger.created_at)
            if sort_order.lower() == "desc":
                query = query.order_by(desc(sort_column))
            else:
                query = query.order_by(asc(sort_column))

            # Get total count
            total = query.count()

            # Apply pagination
            offset = (page - 1) * size
            triggers = query.offset(offset).limit(size).all()

            # Convert to response objects
            trigger_responses = [TriggerResponse.from_orm(trigger) for trigger in triggers]

            return TriggerListResponse(
                triggers=trigger_responses,
                total=total,
                page=page,
                size=size
            )

        except Exception as e:
            self.logger.error(
                "Error listing triggers",
                hotel_id=str(hotel_id),
                error=str(e)
            )
            raise TriggerServiceError(f"Failed to list triggers: {str(e)}")

    def get_trigger_statistics(self, hotel_id: uuid.UUID) -> TriggerStatistics:
        """
        Get trigger statistics for a hotel

        Args:
            hotel_id: Hotel ID for tenant isolation

        Returns:
            TriggerStatistics: Statistics data
        """
        try:
            # Get basic counts
            total_triggers = self.db.query(Trigger).filter(
                Trigger.hotel_id == hotel_id
            ).count()

            active_triggers = self.db.query(Trigger).filter(
                and_(
                    Trigger.hotel_id == hotel_id,
                    Trigger.is_active == True
                )
            ).count()

            inactive_triggers = total_triggers - active_triggers

            # Get triggers by type
            triggers_by_type = {}
            for trigger_type in TriggerType:
                count = self.db.query(Trigger).filter(
                    and_(
                        Trigger.hotel_id == hotel_id,
                        Trigger.trigger_type == trigger_type
                    )
                ).count()
                triggers_by_type[trigger_type.value] = count

            # TODO: Add execution statistics from execution logs
            # For now, return placeholder values
            executions_last_24h = 0
            success_rate = 100.0
            avg_execution_time_ms = 0.0

            return TriggerStatistics(
                total_triggers=total_triggers,
                active_triggers=active_triggers,
                inactive_triggers=inactive_triggers,
                triggers_by_type=triggers_by_type,
                executions_last_24h=executions_last_24h,
                success_rate=success_rate,
                avg_execution_time_ms=avg_execution_time_ms
            )

        except Exception as e:
            self.logger.error(
                "Error getting trigger statistics",
                hotel_id=str(hotel_id),
                error=str(e)
            )
            raise TriggerServiceError(f"Failed to get statistics: {str(e)}")

    def _convert_conditions_to_dict(self, conditions) -> Dict[str, Any]:
        """
        Convert conditions schema to dictionary for storage

        Args:
            conditions: Conditions schema object

        Returns:
            Dict[str, Any]: Conditions as dictionary
        """
        if hasattr(conditions, 'dict'):
            return conditions.dict(exclude_none=True)
        return conditions


def get_trigger_service(db: Session = None) -> TriggerService:
    """
    Get trigger service instance
    
    Args:
        db: Database session
        
    Returns:
        TriggerService: Service instance
    """
    return TriggerService(db)


# Export service and exceptions
__all__ = [
    'TriggerService',
    'TriggerServiceError',
    'TriggerNotFoundError', 
    'TriggerValidationError',
    'TriggerTemplateError',
    'get_trigger_service'
]
