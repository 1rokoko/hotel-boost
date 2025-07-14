"""
Trigger API endpoints for WhatsApp Hotel Bot
"""

import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import structlog

from app.database import get_db
from app.services.trigger_service import (
    TriggerService,
    TriggerServiceError,
    TriggerNotFoundError,
    TriggerValidationError,
    TriggerTemplateError
)
from app.services.trigger_engine import (
    TriggerEngine,
    get_trigger_engine,
    TriggerEngineError,
    TriggerExecutionError
)
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
    TriggerPreview,
    TriggerBulkOperation,
    TriggerBulkResult
)
from app.models.trigger import TriggerType
from app.core.tenant import require_tenant_context
from app.middleware.tenant import get_current_tenant_id

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.post("/", response_model=TriggerResponse, status_code=status.HTTP_201_CREATED)
def create_trigger(
    trigger_data: TriggerCreate,
    hotel_id: uuid.UUID = Depends(get_current_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Create a new trigger
    
    Creates a new trigger with the provided configuration. The trigger will be
    associated with the current hotel context.
    """
    try:
        trigger_service = TriggerService(db)
        trigger_service = TriggerService(db)
        trigger = trigger_service.create_trigger(hotel_id, trigger_data)
        
        logger.info(
            "Trigger created via API",
            trigger_id=str(trigger.id),
            hotel_id=str(hotel_id),
            trigger_name=trigger.name
        )
        
        return trigger
        
    except TriggerValidationError as e:
        logger.warning(
            "Trigger validation failed",
            hotel_id=str(hotel_id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}"
        )
    except TriggerTemplateError as e:
        logger.warning(
            "Trigger template error",
            hotel_id=str(hotel_id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Template error: {str(e)}"
        )
    except TriggerServiceError as e:
        logger.error(
            "Error creating trigger via API",
            hotel_id=str(hotel_id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create trigger"
        )


@router.get("/{trigger_id}", response_model=TriggerResponse)
def get_trigger(
    trigger_id: uuid.UUID = Path(..., description="Trigger ID"),
    hotel_id: uuid.UUID = Depends(get_current_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Get trigger by ID
    
    Retrieves a specific trigger by its ID. The trigger must belong to the
    current hotel context.
    """
    try:
        trigger_service = TriggerService(db)
        trigger_service = TriggerService(db)
        trigger = trigger_service.get_trigger(hotel_id, trigger_id)
        return trigger
        
    except TriggerNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trigger not found"
        )
    except TriggerServiceError as e:
        logger.error(
            "Error retrieving trigger via API",
            hotel_id=str(hotel_id),
            trigger_id=str(trigger_id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve trigger"
        )


@router.put("/{trigger_id}", response_model=TriggerResponse)
def update_trigger(
    trigger_id: uuid.UUID = Path(..., description="Trigger ID"),
    trigger_data: TriggerUpdate = ...,
    hotel_id: uuid.UUID = Depends(get_current_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Update trigger
    
    Updates an existing trigger with the provided data. Only specified fields
    will be updated.
    """
    try:
        trigger_service = TriggerService(db)
        trigger = trigger_service.update_trigger(hotel_id, trigger_id, trigger_data)
        
        logger.info(
            "Trigger updated via API",
            trigger_id=str(trigger_id),
            hotel_id=str(hotel_id)
        )
        
        return trigger
        
    except TriggerNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trigger not found"
        )
    except (TriggerValidationError, TriggerTemplateError) as e:
        logger.warning(
            "Trigger update validation failed",
            hotel_id=str(hotel_id),
            trigger_id=str(trigger_id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}"
        )
    except TriggerServiceError as e:
        logger.error(
            "Error updating trigger via API",
            hotel_id=str(hotel_id),
            trigger_id=str(trigger_id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update trigger"
        )


@router.delete("/{trigger_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trigger(
    trigger_id: uuid.UUID = Path(..., description="Trigger ID"),
    hotel_id: uuid.UUID = Depends(get_current_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Delete trigger
    
    Deletes a trigger permanently. This action cannot be undone.
    """
    try:
        trigger_service = TriggerService(db)
        trigger_service.delete_trigger(hotel_id, trigger_id)
        
        logger.info(
            "Trigger deleted via API",
            trigger_id=str(trigger_id),
            hotel_id=str(hotel_id)
        )
        
        return None
        
    except TriggerNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trigger not found"
        )
    except TriggerServiceError as e:
        logger.error(
            "Error deleting trigger via API",
            hotel_id=str(hotel_id),
            trigger_id=str(trigger_id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete trigger"
        )


@router.get("/", response_model=TriggerListResponse)
def list_triggers(
    trigger_type: Optional[TriggerType] = Query(None, description="Filter by trigger type"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order"),
    hotel_id: uuid.UUID = Depends(get_current_tenant_id),
    db: Session = Depends(get_db)
):
    """
    List triggers with pagination and filtering
    
    Returns a paginated list of triggers for the current hotel with optional
    filtering by type and status.
    """
    try:
        trigger_service = TriggerService(db)
        triggers = trigger_service.list_triggers(
            hotel_id=hotel_id,
            page=page,
            size=size,
            trigger_type=trigger_type,
            is_active=is_active,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        return triggers
        
    except TriggerServiceError as e:
        logger.error(
            "Error listing triggers via API",
            hotel_id=str(hotel_id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list triggers"
        )


@router.post("/{trigger_id}/test", response_model=TriggerTestResult)
async def test_trigger(
    trigger_id: uuid.UUID = Path(..., description="Trigger ID"),
    test_data: TriggerTestData = ...,
    hotel_id: uuid.UUID = Depends(get_current_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Test trigger execution
    
    Tests a trigger with provided test data without actually sending messages.
    Useful for validating trigger configuration and message templates.
    """
    try:
        trigger_service = TriggerService(db)
        # Get trigger
        trigger = trigger_service.get_trigger(hotel_id, trigger_id)
        
        # Execute trigger in test mode
        start_time = datetime.utcnow()
        
        try:
            trigger_engine = TriggerEngine(db)

            # Build test context
            context = {
                'guest': test_data.guest_data or {},
                'test_mode': True,
                **(test_data.context_data or {})
            }

            # Test execution (dry run)
            result = await trigger_engine.execute_trigger(
                trigger_id=trigger_id,
                context=context
            )
            
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return TriggerTestResult(
                success=result.get('success', False),
                conditions_met=True,  # Assume conditions met for test
                rendered_message=result.get('rendered_message'),
                error_message=result.get('error_message'),
                execution_time_ms=execution_time
            )
            
        except TriggerExecutionError as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return TriggerTestResult(
                success=False,
                conditions_met=False,
                rendered_message=None,
                error_message=str(e),
                execution_time_ms=execution_time
            )
        
    except TriggerNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trigger not found"
        )
    except Exception as e:
        logger.error(
            "Error testing trigger via API",
            hotel_id=str(hotel_id),
            trigger_id=str(trigger_id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to test trigger"
        )


@router.get("/statistics", response_model=TriggerStatistics)
def get_trigger_statistics(
    hotel_id: uuid.UUID = Depends(get_current_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Get trigger statistics

    Returns statistics about triggers for the current hotel including counts,
    execution metrics, and performance data.
    """
    try:
        trigger_service = TriggerService(db)
        statistics = trigger_service.get_trigger_statistics(hotel_id)
        return statistics

    except TriggerServiceError as e:
        logger.error(
            "Error getting trigger statistics via API",
            hotel_id=str(hotel_id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get trigger statistics"
        )


@router.post("/validate-template", response_model=TriggerTemplateValidation)
async def validate_template(
    template_data: dict,
    hotel_id: uuid.UUID = Depends(get_current_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Validate trigger template

    Validates a message template for syntax errors and extracts variables.
    Useful for template validation before creating or updating triggers.
    """
    try:
        from app.utils.template_renderer import TemplateRenderer

        template_string = template_data.get('template', '')
        if not template_string:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Template string is required"
            )

        renderer = TemplateRenderer()
        validation = await renderer.validate_template(template_string)

        return validation

    except Exception as e:
        logger.error(
            "Error validating template via API",
            hotel_id=str(hotel_id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to validate template"
        )


@router.post("/bulk-operation", response_model=TriggerBulkResult)
def bulk_trigger_operation(
    operation_data: TriggerBulkOperation,
    hotel_id: uuid.UUID = Depends(get_current_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Perform bulk operations on triggers

    Performs bulk operations (activate, deactivate, delete) on multiple triggers.
    """
    try:
        successful = []
        failed = []

        for trigger_id in operation_data.trigger_ids:
            try:
                trigger_service = TriggerService(db)
                if operation_data.operation == 'activate':
                    trigger_service.update_trigger(
                        hotel_id,
                        trigger_id,
                        TriggerUpdate(is_active=True)
                    )
                elif operation_data.operation == 'deactivate':
                    trigger_service.update_trigger(
                        hotel_id,
                        trigger_id,
                        TriggerUpdate(is_active=False)
                    )
                elif operation_data.operation == 'delete':
                    trigger_service.delete_trigger(hotel_id, trigger_id)

                successful.append(trigger_id)

            except Exception as e:
                failed.append({
                    'trigger_id': str(trigger_id),
                    'error': str(e)
                })

        logger.info(
            "Bulk trigger operation completed",
            hotel_id=str(hotel_id),
            operation=operation_data.operation,
            successful_count=len(successful),
            failed_count=len(failed)
        )

        return TriggerBulkResult(
            successful=successful,
            failed=failed,
            total_processed=len(operation_data.trigger_ids)
        )

    except Exception as e:
        logger.error(
            "Error performing bulk trigger operation via API",
            hotel_id=str(hotel_id),
            operation=operation_data.operation,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to perform bulk operation"
        )


# Export router
__all__ = ['router']
