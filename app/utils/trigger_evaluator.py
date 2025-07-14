"""
Trigger condition evaluator for WhatsApp Hotel Bot application
"""

import re
from datetime import datetime, time, timedelta
from typing import Dict, Any, List, Union, Optional
import structlog

from app.models.trigger import TriggerType
from app.core.logging import get_logger
from app.utils.cron_parser import CronParser

logger = get_logger(__name__)


class TriggerEvaluatorError(Exception):
    """Base exception for trigger evaluator errors"""
    pass


class TriggerEvaluator:
    """Evaluates trigger conditions based on context data"""
    
    def __init__(self):
        """Initialize trigger evaluator"""
        self.logger = logger.bind(service="trigger_evaluator")
        self.cron_parser = CronParser()
    
    async def evaluate_conditions(
        self,
        trigger_type: TriggerType,
        conditions: Dict[str, Any],
        context: Dict[str, Any]
    ) -> bool:
        """
        Evaluate trigger conditions against context
        
        Args:
            trigger_type: Type of trigger
            conditions: Trigger conditions
            context: Context data for evaluation
            
        Returns:
            bool: True if conditions are met
        """
        try:
            if trigger_type == TriggerType.TIME_BASED:
                return await self._evaluate_time_based_conditions(conditions, context)
            elif trigger_type == TriggerType.CONDITION_BASED:
                return await self._evaluate_condition_based_conditions(conditions, context)
            elif trigger_type == TriggerType.EVENT_BASED:
                return await self._evaluate_event_based_conditions(conditions, context)
            else:
                self.logger.warning(f"Unknown trigger type: {trigger_type}")
                return False
                
        except Exception as e:
            self.logger.error(
                "Error evaluating trigger conditions",
                trigger_type=trigger_type.value,
                error=str(e)
            )
            return False
    
    async def _evaluate_time_based_conditions(
        self,
        conditions: Dict[str, Any],
        context: Dict[str, Any]
    ) -> bool:
        """
        Evaluate time-based trigger conditions
        
        Args:
            conditions: Time-based conditions
            context: Context data
            
        Returns:
            bool: True if time conditions are met
        """
        try:
            time_conditions = conditions.get('time_based', {})
            schedule_type = time_conditions.get('schedule_type')
            
            current_time = datetime.utcnow()
            reference_time = context.get('reference_time', current_time)
            
            if isinstance(reference_time, str):
                reference_time = datetime.fromisoformat(reference_time.replace('Z', '+00:00'))
            
            if schedule_type == 'hours_after_checkin':
                hours_after = time_conditions.get('hours_after', 0)
                target_time = reference_time + timedelta(hours=hours_after)
                return current_time >= target_time
            
            elif schedule_type == 'days_after_checkin':
                days_after = time_conditions.get('days_after', 0)
                target_time = reference_time + timedelta(days=days_after)
                return current_time >= target_time
            
            elif schedule_type == 'specific_time':
                specific_time = time_conditions.get('specific_time')
                if specific_time:
                    # Parse time string if needed
                    if isinstance(specific_time, str):
                        target_time = time.fromisoformat(specific_time)
                    else:
                        target_time = specific_time
                    
                    current_time_only = current_time.time()
                    return current_time_only >= target_time
            
            elif schedule_type == 'immediate':
                return True
            
            elif schedule_type == 'cron_expression':
                cron_expr = time_conditions.get('cron_expression')
                if cron_expr:
                    # Check if current time matches cron expression
                    try:
                        parsed_cron = self.cron_parser.parse_cron_expression(cron_expr)
                        return self.cron_parser._time_matches_cron(current_time, parsed_cron)
                    except Exception as e:
                        self.logger.error(
                            "Error evaluating cron expression",
                            cron_expr=cron_expr,
                            error=str(e)
                        )
                        return False
                return False
            
            return False
            
        except Exception as e:
            self.logger.error(
                "Error evaluating time-based conditions",
                error=str(e)
            )
            return False
    
    async def _evaluate_condition_based_conditions(
        self,
        conditions: Dict[str, Any],
        context: Dict[str, Any]
    ) -> bool:
        """
        Evaluate condition-based trigger conditions
        
        Args:
            conditions: Condition-based conditions
            context: Context data
            
        Returns:
            bool: True if all conditions are met
        """
        try:
            condition_data = conditions.get('condition_based', {})
            condition_list = condition_data.get('conditions', [])
            logic = condition_data.get('logic', 'AND')
            
            if not condition_list:
                return True
            
            results = []
            
            for condition in condition_list:
                field_path = condition.get('field')
                operator = condition.get('operator')
                expected_value = condition.get('value')
                
                # Get actual value from context
                actual_value = self._get_nested_value(context, field_path)
                
                # Evaluate condition
                result = self._evaluate_single_condition(
                    actual_value, 
                    operator, 
                    expected_value
                )
                results.append(result)
            
            # Apply logic operator
            if logic == 'AND':
                return all(results)
            elif logic == 'OR':
                return any(results)
            else:
                self.logger.warning(f"Unknown logic operator: {logic}")
                return False
                
        except Exception as e:
            self.logger.error(
                "Error evaluating condition-based conditions",
                error=str(e)
            )
            return False
    
    async def _evaluate_event_based_conditions(
        self,
        conditions: Dict[str, Any],
        context: Dict[str, Any]
    ) -> bool:
        """
        Evaluate event-based trigger conditions
        
        Args:
            conditions: Event-based conditions
            context: Context data
            
        Returns:
            bool: True if event conditions are met
        """
        try:
            event_conditions = conditions.get('event_based', {})
            expected_event_type = event_conditions.get('event_type')
            delay_minutes = event_conditions.get('delay_minutes', 0)
            event_filters = event_conditions.get('event_filters', {})
            
            # Check if the event type matches
            actual_event_type = context.get('event_type')
            if actual_event_type != expected_event_type:
                return False
            
            # Check delay if specified
            if delay_minutes > 0:
                event_time = context.get('event_time')
                if event_time:
                    if isinstance(event_time, str):
                        event_time = datetime.fromisoformat(event_time.replace('Z', '+00:00'))
                    
                    required_time = event_time + timedelta(minutes=delay_minutes)
                    if datetime.utcnow() < required_time:
                        return False
            
            # Apply event filters
            for filter_key, filter_value in event_filters.items():
                context_value = context.get(filter_key)
                if context_value != filter_value:
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(
                "Error evaluating event-based conditions",
                error=str(e)
            )
            return False
    
    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """
        Get nested value from dictionary using dot notation
        
        Args:
            data: Dictionary to search
            path: Dot-separated path (e.g., 'guest.preferences.room_type')
            
        Returns:
            Any: Value at the path, or None if not found
        """
        try:
            keys = path.split('.')
            current = data
            
            for key in keys:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    return None
            
            return current
            
        except Exception:
            return None
    
    def _evaluate_single_condition(
        self,
        actual_value: Any,
        operator: str,
        expected_value: Any
    ) -> bool:
        """
        Evaluate a single condition
        
        Args:
            actual_value: Actual value from context
            operator: Comparison operator
            expected_value: Expected value
            
        Returns:
            bool: True if condition is met
        """
        try:
            if operator == 'equals':
                return actual_value == expected_value
            
            elif operator == 'not_equals':
                return actual_value != expected_value
            
            elif operator == 'greater_than':
                return self._safe_numeric_compare(actual_value, expected_value, lambda a, b: a > b)
            
            elif operator == 'less_than':
                return self._safe_numeric_compare(actual_value, expected_value, lambda a, b: a < b)
            
            elif operator == 'greater_equal':
                return self._safe_numeric_compare(actual_value, expected_value, lambda a, b: a >= b)
            
            elif operator == 'less_equal':
                return self._safe_numeric_compare(actual_value, expected_value, lambda a, b: a <= b)
            
            elif operator == 'contains':
                if isinstance(actual_value, str) and isinstance(expected_value, str):
                    return expected_value.lower() in actual_value.lower()
                elif isinstance(actual_value, (list, tuple)):
                    return expected_value in actual_value
                return False
            
            elif operator == 'not_contains':
                if isinstance(actual_value, str) and isinstance(expected_value, str):
                    return expected_value.lower() not in actual_value.lower()
                elif isinstance(actual_value, (list, tuple)):
                    return expected_value not in actual_value
                return True
            
            elif operator == 'in':
                if isinstance(expected_value, (list, tuple)):
                    return actual_value in expected_value
                return False
            
            elif operator == 'not_in':
                if isinstance(expected_value, (list, tuple)):
                    return actual_value not in expected_value
                return True
            
            elif operator == 'regex':
                if isinstance(actual_value, str) and isinstance(expected_value, str):
                    try:
                        return bool(re.search(expected_value, actual_value))
                    except re.error:
                        return False
                return False
            
            else:
                self.logger.warning(f"Unknown operator: {operator}")
                return False
                
        except Exception as e:
            self.logger.error(
                "Error evaluating single condition",
                operator=operator,
                error=str(e)
            )
            return False
    
    def _safe_numeric_compare(
        self,
        actual_value: Any,
        expected_value: Any,
        compare_func
    ) -> bool:
        """
        Safely compare numeric values
        
        Args:
            actual_value: Actual value
            expected_value: Expected value
            compare_func: Comparison function
            
        Returns:
            bool: Comparison result
        """
        try:
            # Try to convert to numbers
            if isinstance(actual_value, (int, float)) and isinstance(expected_value, (int, float)):
                return compare_func(actual_value, expected_value)
            
            # Try string to number conversion
            if isinstance(actual_value, str):
                try:
                    actual_value = float(actual_value)
                except ValueError:
                    return False
            
            if isinstance(expected_value, str):
                try:
                    expected_value = float(expected_value)
                except ValueError:
                    return False
            
            return compare_func(actual_value, expected_value)
            
        except Exception:
            return False


# Export evaluator and exceptions
__all__ = [
    'TriggerEvaluator',
    'TriggerEvaluatorError'
]
