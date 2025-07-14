"""
Trigger configuration schemas for WhatsApp Hotel Bot application
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum

from pydantic import BaseModel, Field, field_validator
from pydantic.types import constr, conint


class TriggerTemplateVariable(BaseModel):
    """Schema for trigger template variable"""
    name: constr(min_length=1, max_length=100) = Field(
        ..., 
        description="Variable name"
    )
    description: Optional[str] = Field(
        None, 
        description="Variable description"
    )
    type: str = Field(
        default="string", 
        description="Variable type (string, number, boolean, date)"
    )
    required: bool = Field(
        default=False, 
        description="Whether the variable is required"
    )
    default_value: Optional[Any] = Field(
        None, 
        description="Default value for the variable"
    )
    
    @field_validator('name')
    @classmethod
    def validate_variable_name(cls, v):
        """Validate variable name format"""
        if not v.isidentifier():
            raise ValueError("Variable name must be a valid Python identifier")
        return v


class TriggerTemplateValidation(BaseModel):
    """Schema for trigger template validation result"""
    is_valid: bool = Field(..., description="Whether the template is valid")
    variables: List[TriggerTemplateVariable] = Field(
        default_factory=list, 
        description="Variables found in the template"
    )
    errors: List[str] = Field(
        default_factory=list, 
        description="Validation errors"
    )
    warnings: List[str] = Field(
        default_factory=list, 
        description="Validation warnings"
    )


class TriggerPreview(BaseModel):
    """Schema for trigger preview"""
    rendered_message: str = Field(..., description="Rendered message")
    variables_used: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Variables used in rendering"
    )
    conditions_met: bool = Field(..., description="Whether conditions would be met")
    estimated_send_time: Optional[datetime] = Field(
        None, 
        description="Estimated time when trigger would execute"
    )


class TriggerBulkOperation(BaseModel):
    """Schema for bulk trigger operations"""
    trigger_ids: List[uuid.UUID] = Field(
        ..., 
        min_items=1, 
        max_items=100, 
        description="List of trigger IDs"
    )
    operation: str = Field(
        ..., 
        description="Operation to perform (activate, deactivate, delete)"
    )
    
    @field_validator('operation')
    @classmethod
    def validate_operation(cls, v):
        """Validate operation type"""
        allowed_operations = ['activate', 'deactivate', 'delete']
        if v not in allowed_operations:
            raise ValueError(f"Operation must be one of: {allowed_operations}")
        return v


class TriggerBulkResult(BaseModel):
    """Schema for bulk operation result"""
    successful: List[uuid.UUID] = Field(
        default_factory=list, 
        description="Successfully processed trigger IDs"
    )
    failed: List[Dict[str, Any]] = Field(
        default_factory=list, 
        description="Failed trigger IDs with error messages"
    )
    total_processed: int = Field(..., description="Total number of triggers processed")


class TriggerStatistics(BaseModel):
    """Schema for trigger statistics"""
    total_triggers: int = Field(..., description="Total number of triggers")
    active_triggers: int = Field(..., description="Number of active triggers")
    inactive_triggers: int = Field(..., description="Number of inactive triggers")
    triggers_by_type: Dict[str, int] = Field(
        default_factory=dict, 
        description="Trigger count by type"
    )
    executions_last_24h: int = Field(..., description="Executions in last 24 hours")
    success_rate: float = Field(..., description="Success rate percentage")
    avg_execution_time_ms: float = Field(..., description="Average execution time")


class TriggerPerformanceMetrics(BaseModel):
    """Schema for trigger performance metrics"""
    trigger_id: uuid.UUID = Field(..., description="Trigger ID")
    total_executions: int = Field(..., description="Total number of executions")
    successful_executions: int = Field(..., description="Number of successful executions")
    failed_executions: int = Field(..., description="Number of failed executions")
    avg_execution_time_ms: float = Field(..., description="Average execution time")
    last_execution: Optional[datetime] = Field(None, description="Last execution time")
    success_rate: float = Field(..., description="Success rate percentage")


class TriggerScheduleInfo(BaseModel):
    """Schema for trigger schedule information"""
    trigger_id: uuid.UUID = Field(..., description="Trigger ID")
    next_execution: Optional[datetime] = Field(None, description="Next scheduled execution")
    is_scheduled: bool = Field(..., description="Whether trigger is currently scheduled")
    schedule_type: str = Field(..., description="Type of schedule")
    schedule_details: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Schedule configuration details"
    )


class TriggerExportData(BaseModel):
    """Schema for trigger export data"""
    triggers: List[Dict[str, Any]] = Field(..., description="Trigger data")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Export metadata"
    )
    exported_at: datetime = Field(..., description="Export timestamp")
    hotel_id: uuid.UUID = Field(..., description="Hotel ID")


class TriggerImportData(BaseModel):
    """Schema for trigger import data"""
    triggers: List[Dict[str, Any]] = Field(..., description="Trigger data to import")
    overwrite_existing: bool = Field(
        default=False, 
        description="Whether to overwrite existing triggers"
    )
    validate_only: bool = Field(
        default=False, 
        description="Whether to only validate without importing"
    )


class TriggerImportResult(BaseModel):
    """Schema for trigger import result"""
    imported: List[uuid.UUID] = Field(
        default_factory=list, 
        description="Successfully imported trigger IDs"
    )
    skipped: List[Dict[str, Any]] = Field(
        default_factory=list, 
        description="Skipped triggers with reasons"
    )
    errors: List[Dict[str, Any]] = Field(
        default_factory=list, 
        description="Import errors"
    )
    total_processed: int = Field(..., description="Total number of triggers processed")


class TriggerHealthCheck(BaseModel):
    """Schema for trigger system health check"""
    status: str = Field(..., description="Overall health status")
    active_triggers: int = Field(..., description="Number of active triggers")
    scheduled_tasks: int = Field(..., description="Number of scheduled tasks")
    failed_executions_last_hour: int = Field(..., description="Failed executions in last hour")
    queue_length: int = Field(..., description="Current queue length")
    last_check: datetime = Field(..., description="Last health check time")
    issues: List[str] = Field(
        default_factory=list, 
        description="Identified issues"
    )


class TriggerDebugInfo(BaseModel):
    """Schema for trigger debugging information"""
    trigger_id: uuid.UUID = Field(..., description="Trigger ID")
    current_state: str = Field(..., description="Current trigger state")
    last_evaluation: Optional[datetime] = Field(None, description="Last evaluation time")
    evaluation_result: Optional[bool] = Field(None, description="Last evaluation result")
    context_data: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Context data used in last evaluation"
    )
    error_log: List[str] = Field(
        default_factory=list, 
        description="Recent error messages"
    )
    performance_data: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Performance metrics"
    )


# Export all schemas
__all__ = [
    # Template and validation
    'TriggerTemplateVariable', 'TriggerTemplateValidation', 'TriggerPreview',
    
    # Bulk operations
    'TriggerBulkOperation', 'TriggerBulkResult',
    
    # Statistics and metrics
    'TriggerStatistics', 'TriggerPerformanceMetrics', 'TriggerScheduleInfo',
    
    # Import/Export
    'TriggerExportData', 'TriggerImportData', 'TriggerImportResult',
    
    # Health and debugging
    'TriggerHealthCheck', 'TriggerDebugInfo'
]
