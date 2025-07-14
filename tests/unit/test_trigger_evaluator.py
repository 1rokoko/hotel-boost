"""
Unit tests for trigger evaluator
"""

import pytest
from datetime import datetime, timedelta, time
from unittest.mock import Mock, patch

from app.utils.trigger_evaluator import TriggerEvaluator, TriggerEvaluatorError
from app.models.trigger import TriggerType


class TestTriggerEvaluator:
    """Test cases for TriggerEvaluator"""
    
    @pytest.fixture
    def evaluator(self):
        """TriggerEvaluator instance"""
        return TriggerEvaluator()
    
    @pytest.mark.asyncio
    async def test_evaluate_time_based_hours_after_checkin(self, evaluator):
        """Test time-based evaluation for hours after check-in"""
        conditions = {
            "time_based": {
                "schedule_type": "hours_after_checkin",
                "hours_after": 2
            }
        }
        
        # Test case 1: Time has passed
        reference_time = datetime.utcnow() - timedelta(hours=3)
        context = {"reference_time": reference_time}
        
        result = await evaluator._evaluate_time_based_conditions(conditions, context)
        assert result is True
        
        # Test case 2: Time has not passed
        reference_time = datetime.utcnow() - timedelta(hours=1)
        context = {"reference_time": reference_time}
        
        result = await evaluator._evaluate_time_based_conditions(conditions, context)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_evaluate_time_based_days_after_checkin(self, evaluator):
        """Test time-based evaluation for days after check-in"""
        conditions = {
            "time_based": {
                "schedule_type": "days_after_checkin",
                "days_after": 1
            }
        }
        
        # Test case 1: Time has passed
        reference_time = datetime.utcnow() - timedelta(days=2)
        context = {"reference_time": reference_time}
        
        result = await evaluator._evaluate_time_based_conditions(conditions, context)
        assert result is True
        
        # Test case 2: Time has not passed
        reference_time = datetime.utcnow() - timedelta(hours=12)
        context = {"reference_time": reference_time}
        
        result = await evaluator._evaluate_time_based_conditions(conditions, context)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_evaluate_time_based_specific_time(self, evaluator):
        """Test time-based evaluation for specific time"""
        conditions = {
            "time_based": {
                "schedule_type": "specific_time",
                "specific_time": "09:00:00"
            }
        }
        
        # Mock current time to be after 9 AM
        with patch('app.utils.trigger_evaluator.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(2023, 1, 1, 10, 0, 0)
            
            result = await evaluator._evaluate_time_based_conditions(conditions, {})
            assert result is True
        
        # Mock current time to be before 9 AM
        with patch('app.utils.trigger_evaluator.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(2023, 1, 1, 8, 0, 0)
            
            result = await evaluator._evaluate_time_based_conditions(conditions, {})
            assert result is False
    
    @pytest.mark.asyncio
    async def test_evaluate_time_based_immediate(self, evaluator):
        """Test time-based evaluation for immediate execution"""
        conditions = {
            "time_based": {
                "schedule_type": "immediate"
            }
        }
        
        result = await evaluator._evaluate_time_based_conditions(conditions, {})
        assert result is True
    
    @pytest.mark.asyncio
    async def test_evaluate_condition_based_single_condition(self, evaluator):
        """Test condition-based evaluation with single condition"""
        conditions = {
            "condition_based": {
                "conditions": [
                    {
                        "field": "guest.preferences.room_type",
                        "operator": "equals",
                        "value": "suite"
                    }
                ],
                "logic": "AND"
            }
        }
        
        # Test case 1: Condition matches
        context = {
            "guest": {
                "preferences": {
                    "room_type": "suite"
                }
            }
        }
        
        result = await evaluator._evaluate_condition_based_conditions(conditions, context)
        assert result is True
        
        # Test case 2: Condition doesn't match
        context = {
            "guest": {
                "preferences": {
                    "room_type": "standard"
                }
            }
        }
        
        result = await evaluator._evaluate_condition_based_conditions(conditions, context)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_evaluate_condition_based_multiple_conditions_and(self, evaluator):
        """Test condition-based evaluation with multiple AND conditions"""
        conditions = {
            "condition_based": {
                "conditions": [
                    {
                        "field": "guest.preferences.room_type",
                        "operator": "equals",
                        "value": "suite"
                    },
                    {
                        "field": "guest.preferences.vip",
                        "operator": "equals",
                        "value": True
                    }
                ],
                "logic": "AND"
            }
        }
        
        # Test case 1: All conditions match
        context = {
            "guest": {
                "preferences": {
                    "room_type": "suite",
                    "vip": True
                }
            }
        }
        
        result = await evaluator._evaluate_condition_based_conditions(conditions, context)
        assert result is True
        
        # Test case 2: One condition doesn't match
        context = {
            "guest": {
                "preferences": {
                    "room_type": "suite",
                    "vip": False
                }
            }
        }
        
        result = await evaluator._evaluate_condition_based_conditions(conditions, context)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_evaluate_condition_based_multiple_conditions_or(self, evaluator):
        """Test condition-based evaluation with multiple OR conditions"""
        conditions = {
            "condition_based": {
                "conditions": [
                    {
                        "field": "guest.preferences.room_type",
                        "operator": "equals",
                        "value": "suite"
                    },
                    {
                        "field": "guest.preferences.vip",
                        "operator": "equals",
                        "value": True
                    }
                ],
                "logic": "OR"
            }
        }
        
        # Test case 1: One condition matches
        context = {
            "guest": {
                "preferences": {
                    "room_type": "standard",
                    "vip": True
                }
            }
        }
        
        result = await evaluator._evaluate_condition_based_conditions(conditions, context)
        assert result is True
        
        # Test case 2: No conditions match
        context = {
            "guest": {
                "preferences": {
                    "room_type": "standard",
                    "vip": False
                }
            }
        }
        
        result = await evaluator._evaluate_condition_based_conditions(conditions, context)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_evaluate_event_based_matching_event(self, evaluator):
        """Test event-based evaluation with matching event"""
        conditions = {
            "event_based": {
                "event_type": "guest_checkin",
                "delay_minutes": 0
            }
        }
        
        context = {
            "event_type": "guest_checkin",
            "event_time": datetime.utcnow()
        }
        
        result = await evaluator._evaluate_event_based_conditions(conditions, context)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_evaluate_event_based_non_matching_event(self, evaluator):
        """Test event-based evaluation with non-matching event"""
        conditions = {
            "event_based": {
                "event_type": "guest_checkin",
                "delay_minutes": 0
            }
        }
        
        context = {
            "event_type": "guest_checkout",
            "event_time": datetime.utcnow()
        }
        
        result = await evaluator._evaluate_event_based_conditions(conditions, context)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_evaluate_event_based_with_delay(self, evaluator):
        """Test event-based evaluation with delay"""
        conditions = {
            "event_based": {
                "event_type": "guest_checkin",
                "delay_minutes": 60
            }
        }
        
        # Test case 1: Delay has passed
        event_time = datetime.utcnow() - timedelta(minutes=90)
        context = {
            "event_type": "guest_checkin",
            "event_time": event_time
        }
        
        result = await evaluator._evaluate_event_based_conditions(conditions, context)
        assert result is True
        
        # Test case 2: Delay has not passed
        event_time = datetime.utcnow() - timedelta(minutes=30)
        context = {
            "event_type": "guest_checkin",
            "event_time": event_time
        }
        
        result = await evaluator._evaluate_event_based_conditions(conditions, context)
        assert result is False
    
    def test_get_nested_value_success(self, evaluator):
        """Test successful nested value retrieval"""
        data = {
            "guest": {
                "preferences": {
                    "room_type": "suite",
                    "floor": 5
                }
            }
        }
        
        # Test nested access
        result = evaluator._get_nested_value(data, "guest.preferences.room_type")
        assert result == "suite"
        
        result = evaluator._get_nested_value(data, "guest.preferences.floor")
        assert result == 5
        
        # Test single level access
        result = evaluator._get_nested_value(data, "guest")
        assert result == data["guest"]
    
    def test_get_nested_value_not_found(self, evaluator):
        """Test nested value retrieval with non-existent path"""
        data = {
            "guest": {
                "preferences": {
                    "room_type": "suite"
                }
            }
        }
        
        # Test non-existent path
        result = evaluator._get_nested_value(data, "guest.preferences.non_existent")
        assert result is None
        
        result = evaluator._get_nested_value(data, "non_existent.path")
        assert result is None
    
    def test_evaluate_single_condition_equals(self, evaluator):
        """Test single condition evaluation with equals operator"""
        assert evaluator._evaluate_single_condition("suite", "equals", "suite") is True
        assert evaluator._evaluate_single_condition("standard", "equals", "suite") is False
        assert evaluator._evaluate_single_condition(5, "equals", 5) is True
        assert evaluator._evaluate_single_condition(5, "equals", 3) is False
    
    def test_evaluate_single_condition_not_equals(self, evaluator):
        """Test single condition evaluation with not_equals operator"""
        assert evaluator._evaluate_single_condition("suite", "not_equals", "standard") is True
        assert evaluator._evaluate_single_condition("suite", "not_equals", "suite") is False
    
    def test_evaluate_single_condition_numeric_comparisons(self, evaluator):
        """Test single condition evaluation with numeric operators"""
        # Greater than
        assert evaluator._evaluate_single_condition(10, "greater_than", 5) is True
        assert evaluator._evaluate_single_condition(5, "greater_than", 10) is False
        
        # Less than
        assert evaluator._evaluate_single_condition(5, "less_than", 10) is True
        assert evaluator._evaluate_single_condition(10, "less_than", 5) is False
        
        # Greater equal
        assert evaluator._evaluate_single_condition(10, "greater_equal", 10) is True
        assert evaluator._evaluate_single_condition(10, "greater_equal", 5) is True
        assert evaluator._evaluate_single_condition(5, "greater_equal", 10) is False
        
        # Less equal
        assert evaluator._evaluate_single_condition(5, "less_equal", 5) is True
        assert evaluator._evaluate_single_condition(5, "less_equal", 10) is True
        assert evaluator._evaluate_single_condition(10, "less_equal", 5) is False
    
    def test_evaluate_single_condition_contains(self, evaluator):
        """Test single condition evaluation with contains operator"""
        # String contains
        assert evaluator._evaluate_single_condition("hello world", "contains", "world") is True
        assert evaluator._evaluate_single_condition("hello world", "contains", "xyz") is False
        
        # List contains
        assert evaluator._evaluate_single_condition([1, 2, 3], "contains", 2) is True
        assert evaluator._evaluate_single_condition([1, 2, 3], "contains", 5) is False
    
    def test_evaluate_single_condition_in_operator(self, evaluator):
        """Test single condition evaluation with in operator"""
        assert evaluator._evaluate_single_condition("suite", "in", ["suite", "standard"]) is True
        assert evaluator._evaluate_single_condition("deluxe", "in", ["suite", "standard"]) is False
        assert evaluator._evaluate_single_condition(5, "in", [1, 3, 5, 7]) is True
        assert evaluator._evaluate_single_condition(4, "in", [1, 3, 5, 7]) is False
    
    def test_evaluate_single_condition_regex(self, evaluator):
        """Test single condition evaluation with regex operator"""
        assert evaluator._evaluate_single_condition("test@example.com", "regex", r".*@.*\.com") is True
        assert evaluator._evaluate_single_condition("invalid-email", "regex", r".*@.*\.com") is False
        assert evaluator._evaluate_single_condition("ABC123", "regex", r"[A-Z]+\d+") is True
        assert evaluator._evaluate_single_condition("abc123", "regex", r"[A-Z]+\d+") is False
    
    def test_safe_numeric_compare(self, evaluator):
        """Test safe numeric comparison"""
        # Numeric values
        assert evaluator._safe_numeric_compare(10, 5, lambda a, b: a > b) is True
        assert evaluator._safe_numeric_compare(5, 10, lambda a, b: a > b) is False
        
        # String to numeric conversion
        assert evaluator._safe_numeric_compare("10", "5", lambda a, b: a > b) is True
        assert evaluator._safe_numeric_compare("5", "10", lambda a, b: a > b) is False
        
        # Mixed types
        assert evaluator._safe_numeric_compare(10, "5", lambda a, b: a > b) is True
        assert evaluator._safe_numeric_compare("10", 5, lambda a, b: a > b) is True
        
        # Invalid conversions
        assert evaluator._safe_numeric_compare("abc", "5", lambda a, b: a > b) is False
        assert evaluator._safe_numeric_compare(10, "abc", lambda a, b: a > b) is False
