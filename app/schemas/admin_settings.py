"""
Admin Settings Schemas
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class SettingValue(BaseModel):
    """Setting value schema"""
    key: str = Field(..., description="Setting key")
    value: Any = Field(..., description="Setting value")
    description: Optional[str] = Field(None, description="Setting description")
    category: Optional[str] = Field(None, description="Setting category")


class SystemSettingsResponse(BaseModel):
    """System settings response schema"""
    settings: List[SettingValue] = Field(..., description="List of system settings")
    total_count: int = Field(..., description="Total number of settings")
    last_updated: Optional[datetime] = Field(None, description="Last update timestamp")


class SystemSettingsUpdate(BaseModel):
    """System settings update schema"""
    settings: List[SettingValue] = Field(..., description="Settings to update")
    reason: Optional[str] = Field(None, description="Reason for update")


class SettingsHistoryEntry(BaseModel):
    """Settings history entry schema"""
    id: uuid.UUID = Field(..., description="History entry ID")
    setting_key: str = Field(..., description="Setting key")
    old_value: Any = Field(..., description="Previous value")
    new_value: Any = Field(..., description="New value")
    changed_by: uuid.UUID = Field(..., description="User who made the change")
    changed_at: datetime = Field(..., description="When the change was made")
    reason: Optional[str] = Field(None, description="Reason for change")


class SettingsHistoryResponse(BaseModel):
    """Settings history response schema"""
    history: List[SettingsHistoryEntry] = Field(..., description="Settings history")
    total_count: int = Field(..., description="Total number of history entries")
    page: int = Field(..., description="Current page")
    page_size: int = Field(..., description="Page size")
