"""
Trigger engine for WhatsApp Hotel Bot application
"""

import uuid
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Union
from sqlalchemy.orm import Session
from sqlalchemy import and_
import structlog

from app.models.trigger import Trigger, TriggerType
from app.models.hotel import Hotel
from app.models.guest import Guest
from app.services.green_api_service import GreenAPIService
from app.services.message_sender import MessageSender
from app.utils.trigger_evaluator import TriggerEvaluator
from app.utils.template_renderer import TemplateRenderer
from app.core.logging import get_logger
from app.database import get_db

logger = get_logger(__name__)


class TriggerEngineError(Exception):
    """Base exception for trigger engine errors"""
    pass


class TriggerExecutionError(TriggerEngineError):
    """Raised when trigger execution fails"""
    pass


class TriggerEngine:
    """Main engine for trigger evaluation and execution"""
    
    def __init__(self, db: Session):
        """
        Initialize trigger engine
        
        Args:
            db: Database session
        """
        self.db = db
        self.logger = logger.bind(service="trigger_engine")
        self.evaluator = TriggerEvaluator()
        self.template_renderer = TemplateRenderer()
        self.message_sender = MessageSender(db)
    
    async def evaluate_triggers(
        self, 
        hotel_id: uuid.UUID, 
        context: Dict[str, Any],
        trigger_type: Optional[TriggerType] = None
    ) -> List[Dict[str, Any]]:
        """
        Evaluate triggers for a hotel with given context
        
        Args:
            hotel_id: Hotel ID
            context: Context data for evaluation
            trigger_type: Optional filter by trigger type
            
        Returns:
            List[Dict[str, Any]]: List of triggers that should be executed
        """
        try:
            # Get active triggers for the hotel
            query = self.db.query(Trigger).filter(
                and_(
                    Trigger.hotel_id == hotel_id,
                    Trigger.is_active == True
                )
            )
            
            if trigger_type:
                query = query.filter(Trigger.trigger_type == trigger_type)
            
            # Order by priority (1 = highest priority)
            triggers = query.order_by(Trigger.priority.asc()).all()
            
            executable_triggers = []
            
            for trigger in triggers:
                try:
                    # Evaluate trigger conditions
                    should_execute = await self.evaluator.evaluate_conditions(
                        trigger.trigger_type,
                        trigger.conditions,
                        context
                    )
                    
                    if should_execute:
                        executable_triggers.append({
                            'trigger': trigger,
                            'context': context,
                            'evaluation_time': datetime.utcnow()
                        })
                        
                        self.logger.info(
                            "Trigger conditions met",
                            trigger_id=str(trigger.id),
                            hotel_id=str(hotel_id),
                            trigger_name=trigger.name
                        )
                    
                except Exception as e:
                    self.logger.error(
                        "Error evaluating trigger",
                        trigger_id=str(trigger.id),
                        hotel_id=str(hotel_id),
                        error=str(e)
                    )
                    continue
            
            return executable_triggers
            
        except Exception as e:
            self.logger.error(
                "Error evaluating triggers",
                hotel_id=str(hotel_id),
                error=str(e)
            )
            raise TriggerEngineError(f"Failed to evaluate triggers: {str(e)}")
    
    async def execute_trigger(
        self, 
        trigger_id: uuid.UUID, 
        guest_id: Optional[uuid.UUID] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a specific trigger
        
        Args:
            trigger_id: Trigger ID to execute
            guest_id: Optional guest ID for context
            context: Optional additional context
            
        Returns:
            Dict[str, Any]: Execution result
        """
        execution_start = datetime.utcnow()
        
        try:
            # Get trigger
            trigger = self.db.query(Trigger).filter(Trigger.id == trigger_id).first()
            if not trigger:
                raise TriggerExecutionError(f"Trigger {trigger_id} not found")
            
            if not trigger.is_active:
                raise TriggerExecutionError(f"Trigger {trigger_id} is not active")
            
            # Get hotel
            hotel = self.db.query(Hotel).filter(Hotel.id == trigger.hotel_id).first()
            if not hotel:
                raise TriggerExecutionError(f"Hotel {trigger.hotel_id} not found")
            
            # Get guest if provided
            guest = None
            if guest_id:
                guest = self.db.query(Guest).filter(
                    and_(
                        Guest.id == guest_id,
                        Guest.hotel_id == trigger.hotel_id
                    )
                ).first()
                if not guest:
                    raise TriggerExecutionError(f"Guest {guest_id} not found")
            
            # Build context for template rendering
            template_context = self._build_template_context(
                hotel=hotel,
                guest=guest,
                trigger=trigger,
                additional_context=context or {}
            )
            
            # Render message template
            rendered_message = await self.template_renderer.render_template(
                trigger.message_template,
                template_context
            )
            
            # Send message if guest is provided
            message_sent = False
            if guest and guest.phone_number:
                try:
                    await self.message_sender.send_text_message(
                        hotel_id=trigger.hotel_id,
                        phone_number=guest.phone_number,
                        message=rendered_message
                    )
                    message_sent = True
                    
                    self.logger.info(
                        "Trigger message sent successfully",
                        trigger_id=str(trigger_id),
                        guest_id=str(guest_id) if guest_id else None,
                        hotel_id=str(trigger.hotel_id)
                    )
                    
                except Exception as e:
                    self.logger.error(
                        "Failed to send trigger message",
                        trigger_id=str(trigger_id),
                        guest_id=str(guest_id) if guest_id else None,
                        error=str(e)
                    )
                    raise TriggerExecutionError(f"Failed to send message: {str(e)}")
            
            execution_time = (datetime.utcnow() - execution_start).total_seconds() * 1000
            
            result = {
                'trigger_id': trigger_id,
                'guest_id': guest_id,
                'success': True,
                'message_sent': message_sent,
                'rendered_message': rendered_message,
                'execution_time_ms': execution_time,
                'executed_at': execution_start
            }
            
            # TODO: Log execution to database
            
            return result
            
        except TriggerExecutionError:
            raise
        except Exception as e:
            execution_time = (datetime.utcnow() - execution_start).total_seconds() * 1000
            
            self.logger.error(
                "Unexpected error executing trigger",
                trigger_id=str(trigger_id),
                guest_id=str(guest_id) if guest_id else None,
                error=str(e)
            )
            
            result = {
                'trigger_id': trigger_id,
                'guest_id': guest_id,
                'success': False,
                'message_sent': False,
                'error_message': str(e),
                'execution_time_ms': execution_time,
                'executed_at': execution_start
            }
            
            # TODO: Log execution to database
            
            return result
    
    async def schedule_time_based_trigger(
        self, 
        trigger: Trigger, 
        guest: Guest,
        reference_time: Optional[datetime] = None
    ) -> Optional[datetime]:
        """
        Schedule a time-based trigger for execution
        
        Args:
            trigger: Trigger to schedule
            guest: Guest for the trigger
            reference_time: Reference time (defaults to now)
            
        Returns:
            Optional[datetime]: Scheduled execution time
        """
        try:
            if trigger.trigger_type != TriggerType.TIME_BASED:
                raise TriggerEngineError("Trigger is not time-based")
            
            conditions = trigger.conditions
            if not conditions or 'time_based' not in conditions:
                raise TriggerEngineError("Invalid time-based conditions")
            
            time_conditions = conditions['time_based']
            schedule_type = time_conditions.get('schedule_type')
            
            reference_time = reference_time or datetime.utcnow()
            scheduled_time = None
            
            if schedule_type == 'hours_after_checkin':
                hours_after = time_conditions.get('hours_after', 0)
                scheduled_time = reference_time + timedelta(hours=hours_after)
            
            elif schedule_type == 'days_after_checkin':
                days_after = time_conditions.get('days_after', 0)
                scheduled_time = reference_time + timedelta(days=days_after)
            
            elif schedule_type == 'specific_time':
                # TODO: Implement specific time scheduling
                pass
            
            elif schedule_type == 'cron_expression':
                # TODO: Implement cron expression scheduling
                pass
            
            if scheduled_time:
                # TODO: Schedule with Celery
                self.logger.info(
                    "Time-based trigger scheduled",
                    trigger_id=str(trigger.id),
                    guest_id=str(guest.id),
                    scheduled_time=scheduled_time.isoformat()
                )
            
            return scheduled_time
            
        except Exception as e:
            self.logger.error(
                "Error scheduling time-based trigger",
                trigger_id=str(trigger.id),
                guest_id=str(guest.id),
                error=str(e)
            )
            raise TriggerEngineError(f"Failed to schedule trigger: {str(e)}")
    
    def _build_template_context(
        self,
        hotel: Hotel,
        guest: Optional[Guest],
        trigger: Trigger,
        additional_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Build context for template rendering
        
        Args:
            hotel: Hotel object
            guest: Guest object (optional)
            trigger: Trigger object
            additional_context: Additional context data
            
        Returns:
            Dict[str, Any]: Template context
        """
        context = {
            'hotel': {
                'name': hotel.name,
                'whatsapp_number': hotel.whatsapp_number,
                'settings': hotel.settings or {}
            },
            'trigger': {
                'name': trigger.name,
                'type': trigger.trigger_type.value
            },
            'now': datetime.utcnow(),
            **additional_context
        }
        
        if guest:
            context['guest'] = {
                'name': guest.name or 'Guest',
                'phone_number': guest.phone_number,
                'preferences': guest.preferences or {},
                'created_at': guest.created_at
            }
        
        return context


def get_trigger_engine(db: Session = None) -> TriggerEngine:
    """
    Get trigger engine instance
    
    Args:
        db: Database session
        
    Returns:
        TriggerEngine: Engine instance
    """
    return TriggerEngine(db)


# Export engine and exceptions
__all__ = [
    'TriggerEngine',
    'TriggerEngineError',
    'TriggerExecutionError',
    'get_trigger_engine'
]
