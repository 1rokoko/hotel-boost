"""
Celery tasks for trigger execution
"""

import uuid
from typing import Optional, Dict, Any
from datetime import datetime
import structlog
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app, high_priority_task
from app.database import get_db
from app.services.trigger_engine import TriggerEngine, TriggerEngineError
from app.models.trigger import Trigger
from app.models.hotel import Hotel
from app.models.guest import Guest

logger = structlog.get_logger(__name__)


@celery_app.task(bind=True, max_retries=3)
def execute_trigger_task(
    self,
    trigger_id: str,
    guest_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None
):
    """
    Execute a trigger asynchronously
    
    Args:
        trigger_id: ID of the trigger to execute
        guest_id: Optional guest ID for context
        context: Optional additional context
        correlation_id: Correlation ID for tracking
    """
    correlation_id = correlation_id or str(uuid.uuid4())
    
    try:
        # Get database session
        db: Session = next(get_db())
        
        # Create trigger engine
        trigger_engine = TriggerEngine(db)
        
        # Convert string IDs to UUIDs
        trigger_uuid = uuid.UUID(trigger_id)
        guest_uuid = uuid.UUID(guest_id) if guest_id else None
        
        logger.info(
            "Starting trigger execution",
            trigger_id=trigger_id,
            guest_id=guest_id,
            correlation_id=correlation_id
        )
        
        # Execute trigger
        result = trigger_engine.execute_trigger(
            trigger_id=trigger_uuid,
            guest_id=guest_uuid,
            context=context or {}
        )
        
        if result.get('success'):
            logger.info(
                "Trigger executed successfully",
                trigger_id=trigger_id,
                guest_id=guest_id,
                correlation_id=correlation_id,
                execution_time_ms=result.get('execution_time_ms')
            )
        else:
            logger.error(
                "Trigger execution failed",
                trigger_id=trigger_id,
                guest_id=guest_id,
                correlation_id=correlation_id,
                error=result.get('error_message')
            )
        
        return result
        
    except TriggerEngineError as e:
        logger.error(
            "Trigger engine error",
            trigger_id=trigger_id,
            guest_id=guest_id,
            correlation_id=correlation_id,
            error=str(e)
        )
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            retry_delay = 2 ** self.request.retries
            logger.info(
                "Retrying trigger execution",
                trigger_id=trigger_id,
                retry_count=self.request.retries + 1,
                retry_delay=retry_delay
            )
            raise self.retry(countdown=retry_delay, exc=e)
        
        # Max retries exceeded
        logger.error(
            "Max retries exceeded for trigger execution",
            trigger_id=trigger_id,
            guest_id=guest_id,
            correlation_id=correlation_id
        )
        
        return {
            'trigger_id': trigger_id,
            'guest_id': guest_id,
            'success': False,
            'error_message': f"Max retries exceeded: {str(e)}",
            'correlation_id': correlation_id
        }
        
    except Exception as e:
        logger.error(
            "Unexpected error in trigger execution task",
            trigger_id=trigger_id,
            guest_id=guest_id,
            correlation_id=correlation_id,
            error=str(e)
        )
        
        return {
            'trigger_id': trigger_id,
            'guest_id': guest_id,
            'success': False,
            'error_message': f"Unexpected error: {str(e)}",
            'correlation_id': correlation_id
        }


@high_priority_task(bind=True, max_retries=2)
def execute_time_based_trigger_task(
    self,
    trigger_id: str,
    guest_id: str,
    scheduled_time: str,
    correlation_id: Optional[str] = None
):
    """
    Execute a time-based trigger at scheduled time
    
    Args:
        trigger_id: ID of the trigger to execute
        guest_id: Guest ID for the trigger
        scheduled_time: ISO format scheduled time
        correlation_id: Correlation ID for tracking
    """
    correlation_id = correlation_id or str(uuid.uuid4())
    
    try:
        # Parse scheduled time
        scheduled_dt = datetime.fromisoformat(scheduled_time.replace('Z', '+00:00'))
        
        logger.info(
            "Executing scheduled time-based trigger",
            trigger_id=trigger_id,
            guest_id=guest_id,
            scheduled_time=scheduled_time,
            correlation_id=correlation_id
        )
        
        # Add scheduling context
        context = {
            'scheduled_time': scheduled_dt,
            'trigger_type': 'time_based',
            'execution_reason': 'scheduled'
        }
        
        # Execute the trigger
        return execute_trigger_task.apply_async(
            args=[trigger_id, guest_id, context, correlation_id]
        ).get()
        
    except Exception as e:
        logger.error(
            "Error executing time-based trigger",
            trigger_id=trigger_id,
            guest_id=guest_id,
            scheduled_time=scheduled_time,
            correlation_id=correlation_id,
            error=str(e)
        )
        
        return {
            'trigger_id': trigger_id,
            'guest_id': guest_id,
            'success': False,
            'error_message': f"Time-based trigger error: {str(e)}",
            'correlation_id': correlation_id
        }


@celery_app.task(bind=True)
def evaluate_event_triggers_task(
    self,
    hotel_id: str,
    event_type: str,
    event_data: Dict[str, Any],
    correlation_id: Optional[str] = None
):
    """
    Evaluate and execute event-based triggers
    
    Args:
        hotel_id: Hotel ID where the event occurred
        event_type: Type of event that occurred
        event_data: Event data for context
        correlation_id: Correlation ID for tracking
    """
    correlation_id = correlation_id or str(uuid.uuid4())
    
    try:
        # Get database session
        db: Session = next(get_db())
        
        # Create trigger engine
        trigger_engine = TriggerEngine(db)
        
        # Convert hotel ID to UUID
        hotel_uuid = uuid.UUID(hotel_id)
        
        logger.info(
            "Evaluating event triggers",
            hotel_id=hotel_id,
            event_type=event_type,
            correlation_id=correlation_id
        )
        
        # Build context for evaluation
        context = {
            'event_type': event_type,
            'event_time': datetime.utcnow(),
            'hotel_id': hotel_uuid,
            **event_data
        }
        
        # Evaluate triggers for this event
        executable_triggers = trigger_engine.evaluate_triggers(
            hotel_id=hotel_uuid,
            context=context,
            trigger_type='event_based'
        )
        
        executed_count = 0
        
        # Execute each qualifying trigger
        for trigger_info in executable_triggers:
            trigger = trigger_info['trigger']
            guest_id = event_data.get('guest_id')
            
            try:
                # Execute trigger asynchronously
                execute_trigger_task.delay(
                    trigger_id=str(trigger.id),
                    guest_id=guest_id,
                    context=context,
                    correlation_id=correlation_id
                )
                executed_count += 1
                
            except Exception as e:
                logger.error(
                    "Error scheduling trigger execution",
                    trigger_id=str(trigger.id),
                    guest_id=guest_id,
                    error=str(e)
                )
        
        logger.info(
            "Event trigger evaluation completed",
            hotel_id=hotel_id,
            event_type=event_type,
            triggers_found=len(executable_triggers),
            triggers_executed=executed_count,
            correlation_id=correlation_id
        )
        
        return {
            'hotel_id': hotel_id,
            'event_type': event_type,
            'triggers_found': len(executable_triggers),
            'triggers_executed': executed_count,
            'correlation_id': correlation_id
        }
        
    except Exception as e:
        logger.error(
            "Error evaluating event triggers",
            hotel_id=hotel_id,
            event_type=event_type,
            correlation_id=correlation_id,
            error=str(e)
        )
        
        return {
            'hotel_id': hotel_id,
            'event_type': event_type,
            'success': False,
            'error_message': str(e),
            'correlation_id': correlation_id
        }


@celery_app.task(bind=True)
def cleanup_expired_scheduled_triggers_task(self):
    """
    Cleanup expired scheduled triggers
    
    This task runs periodically to clean up triggers that were scheduled
    but never executed due to system issues.
    """
    try:
        # Get database session
        db: Session = next(get_db())
        
        logger.info("Starting cleanup of expired scheduled triggers")
        
        # TODO: Implement cleanup logic
        # This would involve:
        # 1. Finding scheduled triggers that are past their execution time
        # 2. Checking if they were actually executed
        # 3. Cleaning up orphaned schedule entries
        
        logger.info("Cleanup of expired scheduled triggers completed")
        
        return {
            'success': True,
            'cleaned_up_count': 0  # Placeholder
        }
        
    except Exception as e:
        logger.error(
            "Error cleaning up expired scheduled triggers",
            error=str(e)
        )
        
        return {
            'success': False,
            'error_message': str(e)
        }


# Export task functions
__all__ = [
    'execute_trigger_task',
    'execute_time_based_trigger_task',
    'evaluate_event_triggers_task',
    'cleanup_expired_scheduled_triggers_task'
]
