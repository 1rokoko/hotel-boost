"""
Cron expression parser for WhatsApp Hotel Bot application
"""

import re
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
import structlog

from app.core.logging import get_logger

logger = get_logger(__name__)


class CronParserError(Exception):
    """Base exception for cron parser errors"""
    pass


class CronParser:
    """Parser for cron expressions"""
    
    def __init__(self):
        """Initialize cron parser"""
        self.logger = logger.bind(service="cron_parser")
    
    def parse_cron_expression(self, cron_expr: str) -> dict:
        """
        Parse a cron expression into its components
        
        Args:
            cron_expr: Cron expression (e.g., "0 9 * * 1-5")
            
        Returns:
            dict: Parsed cron components
            
        Raises:
            CronParserError: If expression is invalid
        """
        try:
            # Remove extra whitespace and split
            parts = cron_expr.strip().split()
            
            if len(parts) != 5:
                raise CronParserError(
                    f"Invalid cron expression: expected 5 parts, got {len(parts)}"
                )
            
            minute, hour, day, month, weekday = parts
            
            return {
                'minute': self._parse_field(minute, 0, 59, 'minute'),
                'hour': self._parse_field(hour, 0, 23, 'hour'),
                'day': self._parse_field(day, 1, 31, 'day'),
                'month': self._parse_field(month, 1, 12, 'month'),
                'weekday': self._parse_field(weekday, 0, 6, 'weekday')
            }
            
        except CronParserError:
            raise
        except Exception as e:
            raise CronParserError(f"Error parsing cron expression: {str(e)}")
    
    def _parse_field(self, field: str, min_val: int, max_val: int, field_name: str) -> List[int]:
        """
        Parse a single cron field
        
        Args:
            field: Field value (e.g., "*/5", "1-3", "1,3,5")
            min_val: Minimum allowed value
            max_val: Maximum allowed value
            field_name: Name of the field for error messages
            
        Returns:
            List[int]: List of valid values for this field
        """
        try:
            # Handle wildcard
            if field == '*':
                return list(range(min_val, max_val + 1))
            
            # Handle step values (e.g., */5, 1-10/2)
            if '/' in field:
                return self._parse_step_field(field, min_val, max_val, field_name)
            
            # Handle ranges (e.g., 1-5)
            if '-' in field:
                return self._parse_range_field(field, min_val, max_val, field_name)
            
            # Handle lists (e.g., 1,3,5)
            if ',' in field:
                return self._parse_list_field(field, min_val, max_val, field_name)
            
            # Handle single value
            try:
                value = int(field)
                if min_val <= value <= max_val:
                    return [value]
                else:
                    raise CronParserError(
                        f"Value {value} out of range for {field_name} ({min_val}-{max_val})"
                    )
            except ValueError:
                raise CronParserError(f"Invalid value '{field}' for {field_name}")
                
        except CronParserError:
            raise
        except Exception as e:
            raise CronParserError(f"Error parsing {field_name} field '{field}': {str(e)}")
    
    def _parse_step_field(self, field: str, min_val: int, max_val: int, field_name: str) -> List[int]:
        """Parse step field (e.g., */5, 1-10/2)"""
        parts = field.split('/')
        if len(parts) != 2:
            raise CronParserError(f"Invalid step format in {field_name}: {field}")
        
        range_part, step_part = parts
        
        try:
            step = int(step_part)
            if step <= 0:
                raise CronParserError(f"Step value must be positive in {field_name}: {step}")
        except ValueError:
            raise CronParserError(f"Invalid step value in {field_name}: {step_part}")
        
        # Get base range
        if range_part == '*':
            base_values = list(range(min_val, max_val + 1))
        elif '-' in range_part:
            base_values = self._parse_range_field(range_part, min_val, max_val, field_name)
        else:
            try:
                start_val = int(range_part)
                if min_val <= start_val <= max_val:
                    base_values = list(range(start_val, max_val + 1))
                else:
                    raise CronParserError(
                        f"Start value {start_val} out of range for {field_name}"
                    )
            except ValueError:
                raise CronParserError(f"Invalid start value in {field_name}: {range_part}")
        
        # Apply step
        return [val for i, val in enumerate(base_values) if i % step == 0]
    
    def _parse_range_field(self, field: str, min_val: int, max_val: int, field_name: str) -> List[int]:
        """Parse range field (e.g., 1-5)"""
        parts = field.split('-')
        if len(parts) != 2:
            raise CronParserError(f"Invalid range format in {field_name}: {field}")
        
        try:
            start = int(parts[0])
            end = int(parts[1])
        except ValueError:
            raise CronParserError(f"Invalid range values in {field_name}: {field}")
        
        if start > end:
            raise CronParserError(f"Range start > end in {field_name}: {field}")
        
        if not (min_val <= start <= max_val and min_val <= end <= max_val):
            raise CronParserError(
                f"Range values out of bounds in {field_name}: {field} (valid: {min_val}-{max_val})"
            )
        
        return list(range(start, end + 1))
    
    def _parse_list_field(self, field: str, min_val: int, max_val: int, field_name: str) -> List[int]:
        """Parse list field (e.g., 1,3,5)"""
        parts = field.split(',')
        values = []
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
                
            try:
                value = int(part)
                if min_val <= value <= max_val:
                    if value not in values:  # Avoid duplicates
                        values.append(value)
                else:
                    raise CronParserError(
                        f"Value {value} out of range for {field_name} ({min_val}-{max_val})"
                    )
            except ValueError:
                raise CronParserError(f"Invalid value '{part}' in {field_name} list")
        
        return sorted(values)
    
    def get_next_execution_time(
        self, 
        cron_expr: str, 
        from_time: Optional[datetime] = None
    ) -> Optional[datetime]:
        """
        Get the next execution time for a cron expression
        
        Args:
            cron_expr: Cron expression
            from_time: Start time (defaults to now)
            
        Returns:
            Optional[datetime]: Next execution time
        """
        try:
            from_time = from_time or datetime.utcnow()
            parsed = self.parse_cron_expression(cron_expr)
            
            # Start from the next minute
            next_time = from_time.replace(second=0, microsecond=0) + timedelta(minutes=1)
            
            # Find next valid time (limit search to avoid infinite loops)
            max_iterations = 366 * 24 * 60  # One year worth of minutes
            
            for _ in range(max_iterations):
                if self._time_matches_cron(next_time, parsed):
                    return next_time
                next_time += timedelta(minutes=1)
            
            # If we get here, no valid time found in the next year
            self.logger.warning(
                "No valid execution time found for cron expression",
                cron_expr=cron_expr,
                from_time=from_time.isoformat()
            )
            return None
            
        except CronParserError as e:
            self.logger.error(
                "Error calculating next execution time",
                cron_expr=cron_expr,
                error=str(e)
            )
            return None
    
    def _time_matches_cron(self, dt: datetime, parsed_cron: dict) -> bool:
        """
        Check if a datetime matches the parsed cron expression
        
        Args:
            dt: Datetime to check
            parsed_cron: Parsed cron expression
            
        Returns:
            bool: True if time matches
        """
        return (
            dt.minute in parsed_cron['minute'] and
            dt.hour in parsed_cron['hour'] and
            dt.day in parsed_cron['day'] and
            dt.month in parsed_cron['month'] and
            dt.weekday() in parsed_cron['weekday']
        )
    
    def validate_cron_expression(self, cron_expr: str) -> Tuple[bool, Optional[str]]:
        """
        Validate a cron expression
        
        Args:
            cron_expr: Cron expression to validate
            
        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
        """
        try:
            self.parse_cron_expression(cron_expr)
            return True, None
        except CronParserError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"
    
    def get_cron_description(self, cron_expr: str) -> str:
        """
        Get human-readable description of cron expression
        
        Args:
            cron_expr: Cron expression
            
        Returns:
            str: Human-readable description
        """
        try:
            parsed = self.parse_cron_expression(cron_expr)
            
            # Build description parts
            parts = []
            
            # Minute
            if len(parsed['minute']) == 1:
                parts.append(f"at minute {parsed['minute'][0]}")
            elif len(parsed['minute']) == 60:
                parts.append("every minute")
            else:
                parts.append(f"at minutes {', '.join(map(str, parsed['minute']))}")
            
            # Hour
            if len(parsed['hour']) == 1:
                parts.append(f"hour {parsed['hour'][0]}")
            elif len(parsed['hour']) == 24:
                parts.append("every hour")
            else:
                parts.append(f"hours {', '.join(map(str, parsed['hour']))}")
            
            # Day
            if len(parsed['day']) == 31:
                parts.append("every day")
            else:
                parts.append(f"on days {', '.join(map(str, parsed['day']))}")
            
            # Month
            if len(parsed['month']) == 12:
                parts.append("every month")
            else:
                month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
                months = [month_names[m-1] for m in parsed['month']]
                parts.append(f"in {', '.join(months)}")
            
            # Weekday
            if len(parsed['weekday']) == 7:
                parts.append("every weekday")
            else:
                weekday_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
                weekdays = [weekday_names[w] for w in parsed['weekday']]
                parts.append(f"on {', '.join(weekdays)}")
            
            return " ".join(parts)
            
        except CronParserError:
            return f"Invalid cron expression: {cron_expr}"


# Export parser and exceptions
__all__ = [
    'CronParser',
    'CronParserError'
]
