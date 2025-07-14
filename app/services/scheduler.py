"""
Trigger scheduler service for WhatsApp Hotel Bot application
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
import structlog

from app.models.trigger import Trigger, TriggerType
from app.models.guest import Guest
from app.tasks.execute_triggers import (
    execute_time_based_trigger_task,
    evaluate_event_triggers_task
)
from app.core.logging import get_logger

logger = get_logger(__name__)


class TriggerSchedulerError(Exception):
    """Base exception for trigger scheduler errors"""
    pass


class TriggerScheduler:
    """Service for scheduling trigger execution"""
    
    def __init__(self, db: Session):
        """
        Initialize trigger scheduler
        
        Args:
            db: Database session
        """
        self.db = db
        self.logger = logger.bind(service="trigger_scheduler")
    
    async def schedule_trigger(
        self,
        trigger: Trigger,
        execute_at: datetime,
        guest_id: Optional[uuid.UUID] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Schedule a trigger for execution at a specific time
        
        Args:
            trigger: Trigger to schedule
            execute_at: When to execute the trigger
            guest_id: Optional guest ID for context
            context: Optional additional context
            
        Returns:
            str: Task ID for the scheduled execution
        """
        try:
            correlation_id = str(uuid.uuid4())
            
            # Calculate delay until execution
            delay = (execute_at - datetime.utcnow()).total_seconds()
            
            if delay <= 0:
                # Execute immediately if time has passed
                self.logger.warning(
                    "Scheduled time is in the past, executing immediately",
                    trigger_id=str(trigger.id),
                    scheduled_time=execute_at.isoformat(),
                    delay=delay
                )
                delay = 0
            
            # Schedule the task
            task = execute_time_based_trigger_task.apply_async(
                args=[
                    str(trigger.id),
                    str(guest_id) if guest_id else None,
                    execute_at.isoformat(),
                    correlation_id
                ],
                countdown=delay
            )
            
            self.logger.info(
                "Trigger scheduled successfully",
                trigger_id=str(trigger.id),
                guest_id=str(guest_id) if guest_id else None,
                execute_at=execute_at.isoformat(),
                delay_seconds=delay,
                task_id=task.id,
                correlation_id=correlation_id
            )
            
            return task.id
            
        except Exception as e:
            self.logger.error(
                "Error scheduling trigger",
                trigger_id=str(trigger.id),
                guest_id=str(guest_id) if guest_id else None,
                execute_at=execute_at.isoformat(),
                error=str(e)
            )
            raise TriggerSchedulerError(f"Failed to schedule trigger: {str(e)}")
    
    async def cancel_scheduled_trigger(self, task_id: str) -> bool:
        """
        Cancel a scheduled trigger
        
        Args:
            task_id: Task ID of the scheduled trigger
            
        Returns:
            bool: True if cancelled successfully
        """
        try:
            from app.core.celery_app import celery_app
            
            # Revoke the task
            celery_app.control.revoke(task_id, terminate=True)
            
            self.logger.info(
                "Scheduled trigger cancelled",
                task_id=task_id
            )
            
            return True
            
        except Exception as e:
            self.logger.error(
                "Error cancelling scheduled trigger",
                task_id=task_id,
                error=str(e)
            )
            return False
    
    async def reschedule_trigger(
        self,
        task_id: str,
        trigger: Trigger,
        new_time: datetime,
        guest_id: Optional[uuid.UUID] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Reschedule a trigger to a new time
        
        Args:
            task_id: Current task ID to cancel
            trigger: Trigger to reschedule
            new_time: New execution time
            guest_id: Optional guest ID for context
            context: Optional additional context
            
        Returns:
            str: New task ID
        """
        try:
            # Cancel existing schedule
            await self.cancel_scheduled_trigger(task_id)
            
            # Schedule at new time
            new_task_id = await self.schedule_trigger(
                trigger=trigger,
                execute_at=new_time,
                guest_id=guest_id,
                context=context
            )
            
            self.logger.info(
                "Trigger rescheduled successfully",
                trigger_id=str(trigger.id),
                old_task_id=task_id,
                new_task_id=new_task_id,
                new_time=new_time.isoformat()
            )
            
            return new_task_id
            
        except Exception as e:
            self.logger.error(
                "Error rescheduling trigger",
                trigger_id=str(trigger.id),
                task_id=task_id,
                new_time=new_time.isoformat(),
                error=str(e)
            )
            raise TriggerSchedulerError(f"Failed to reschedule trigger: {str(e)}")
    
    async def schedule_time_based_triggers_for_guest(
        self,
        guest: Guest,
        reference_time: Optional[datetime] = None
    ) -> List[str]:
        """
        Schedule all applicable time-based triggers for a guest
        
        Args:
            guest: Guest to schedule triggers for
            reference_time: Reference time (defaults to now)
            
        Returns:
            List[str]: List of scheduled task IDs
        """
        try:
            reference_time = reference_time or datetime.utcnow()
            scheduled_tasks = []
            
            # Get active time-based triggers for the hotel
            triggers = self.db.query(Trigger).filter(
                Trigger.hotel_id == guest.hotel_id,
                Trigger.trigger_type == TriggerType.TIME_BASED,
                Trigger.is_active == True
            ).all()
            
            for trigger in triggers:
                try:
                    # Calculate execution time based on trigger conditions
                    execution_time = self._calculate_execution_time(
                        trigger, 
                        reference_time
                    )
                    
                    if execution_time:
                        task_id = await self.schedule_trigger(
                            trigger=trigger,
                            execute_at=execution_time,
                            guest_id=guest.id,
                            context={
                                'reference_time': reference_time,
                                'guest_checkin_time': reference_time
                            }
                        )
                        scheduled_tasks.append(task_id)
                    
                except Exception as e:
                    self.logger.error(
                        "Error scheduling individual trigger for guest",
                        trigger_id=str(trigger.id),
                        guest_id=str(guest.id),
                        error=str(e)
                    )
                    continue
            
            self.logger.info(
                "Time-based triggers scheduled for guest",
                guest_id=str(guest.id),
                hotel_id=str(guest.hotel_id),
                triggers_scheduled=len(scheduled_tasks)
            )
            
            return scheduled_tasks
            
        except Exception as e:
            self.logger.error(
                "Error scheduling time-based triggers for guest",
                guest_id=str(guest.id),
                error=str(e)
            )
            raise TriggerSchedulerError(f"Failed to schedule triggers for guest: {str(e)}")
    
    async def trigger_event(
        self,
        hotel_id: uuid.UUID,
        event_type: str,
        event_data: Dict[str, Any]
    ) -> str:
        """
        Trigger evaluation of event-based triggers
        
        Args:
            hotel_id: Hotel ID where the event occurred
            event_type: Type of event
            event_data: Event data
            
        Returns:
            str: Task ID for the evaluation
        """
        try:
            correlation_id = str(uuid.uuid4())
            
            # Schedule event trigger evaluation
            task = evaluate_event_triggers_task.delay(
                hotel_id=str(hotel_id),
                event_type=event_type,
                event_data=event_data,
                correlation_id=correlation_id
            )
            
            self.logger.info(
                "Event trigger evaluation scheduled",
                hotel_id=str(hotel_id),
                event_type=event_type,
                task_id=task.id,
                correlation_id=correlation_id
            )
            
            return task.id
            
        except Exception as e:
            self.logger.error(
                "Error triggering event evaluation",
                hotel_id=str(hotel_id),
                event_type=event_type,
                error=str(e)
            )
            raise TriggerSchedulerError(f"Failed to trigger event evaluation: {str(e)}")
    
    def _calculate_execution_time(
        self,
        trigger: Trigger,
        reference_time: datetime
    ) -> Optional[datetime]:
        """
        Calculate execution time for a time-based trigger
        
        Args:
            trigger: Time-based trigger
            reference_time: Reference time for calculation
            
        Returns:
            Optional[datetime]: Calculated execution time
        """
        try:
            conditions = trigger.conditions
            if not conditions or 'time_based' not in conditions:
                return None
            
            time_conditions = conditions['time_based']
            schedule_type = time_conditions.get('schedule_type')
            
            if schedule_type == 'hours_after_checkin':
                hours_after = time_conditions.get('hours_after', 0)
                return reference_time + timedelta(hours=hours_after)
            
            elif schedule_type == 'days_after_checkin':
                days_after = time_conditions.get('days_after', 0)
                return reference_time + timedelta(days=days_after)
            
            elif schedule_type == 'immediate':
                return reference_time
            
            # TODO: Implement specific_time and cron_expression
            
            return None
            
        except Exception as e:
            self.logger.error(
                "Error calculating execution time",
                trigger_id=str(trigger.id),
                error=str(e)
            )
            return None


def get_trigger_scheduler(db: Session = None) -> TriggerScheduler:
    """
    Get trigger scheduler instance
    
    Args:
        db: Database session
        
    Returns:
        TriggerScheduler: Scheduler instance
    """
    return TriggerScheduler(db)


# Export scheduler and exceptions
__all__ = [
    'TriggerScheduler',
    'TriggerSchedulerError',
    'get_trigger_scheduler'
]
