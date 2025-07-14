"""
Template schemas for WhatsApp Hotel Bot API
"""

import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator

from app.models.message_template import TemplateCategory


class TemplateBase(BaseModel):
    """Base template schema"""
    name: str = Field(..., min_length=1, max_length=255, description="Template name")
    category: TemplateCategory = Field(..., description="Template category")
    content: str = Field(..., min_length=1, max_length=4096, description="Template content with Jinja2 syntax")
    variables: Optional[List[str]] = Field(default=[], description="List of variable names used in template")
    language: Optional[str] = Field(default="en", pattern=r"^[a-z]{2}(-[A-Z]{2})?$", description="Language code (ISO 639-1)")
    description: Optional[str] = Field(None, max_length=1000, description="Template description")
    is_active: Optional[bool] = Field(default=True, description="Whether template is active")

    @field_validator('content')
    @classmethod
    def validate_content(cls, v):
        """Validate template content"""
        if not v or not v.strip():
            raise ValueError("Template content cannot be empty")

        # Basic Jinja2 syntax validation
        if v.count('{{') != v.count('}}'):
            raise ValueError("Unmatched Jinja2 variable delimiters")

        if v.count('{%') != v.count('%}'):
            raise ValueError("Unmatched Jinja2 block delimiters")

        return v.strip()

    @field_validator('variables')
    @classmethod
    def validate_variables(cls, v):
        """Validate variable names"""
        if v is None:
            return []

        for var in v:
            if not isinstance(var, str) or not var.strip():
                raise ValueError("Variable names must be non-empty strings")

            # Check for valid variable name format
            if not var.replace('_', '').replace('-', '').isalnum():
                raise ValueError(f"Invalid variable name format: {var}")

        return list(set(v))  # Remove duplicates


class TemplateCreate(TemplateBase):
    """Schema for creating a new template"""
    pass


class TemplateUpdate(BaseModel):
    """Schema for updating a template"""
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Template name")
    category: Optional[TemplateCategory] = Field(None, description="Template category")
    content: Optional[str] = Field(None, min_length=1, max_length=4096, description="Template content")
    variables: Optional[List[str]] = Field(None, description="List of variable names")
    language: Optional[str] = Field(None, pattern=r"^[a-z]{2}(-[A-Z]{2})?$", description="Language code")
    description: Optional[str] = Field(None, max_length=1000, description="Template description")
    is_active: Optional[bool] = Field(None, description="Whether template is active")

    @field_validator('content')
    @classmethod
    def validate_content(cls, v):
        """Validate template content if provided"""
        if v is not None:
            if not v.strip():
                raise ValueError("Template content cannot be empty")

            # Basic Jinja2 syntax validation
            if v.count('{{') != v.count('}}'):
                raise ValueError("Unmatched Jinja2 variable delimiters")

            if v.count('{%') != v.count('%}'):
                raise ValueError("Unmatched Jinja2 block delimiters")

            return v.strip()
        return v

    @field_validator('variables')
    @classmethod
    def validate_variables(cls, v):
        """Validate variable names if provided"""
        if v is not None:
            for var in v:
                if not isinstance(var, str) or not var.strip():
                    raise ValueError("Variable names must be non-empty strings")

                # Check for valid variable name format
                if not var.replace('_', '').replace('-', '').isalnum():
                    raise ValueError(f"Invalid variable name format: {var}")

            return list(set(v))  # Remove duplicates
        return v


class TemplateResponse(TemplateBase):
    """Schema for template response"""
    id: uuid.UUID = Field(..., description="Template ID")
    hotel_id: uuid.UUID = Field(..., description="Hotel ID")
    usage_count: Dict[str, Any] = Field(default={}, description="Usage statistics")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        orm_mode = True


class TemplateListResponse(BaseModel):
    """Schema for template list response"""
    templates: List[TemplateResponse] = Field(..., description="List of templates")
    total: int = Field(..., description="Total number of templates")
    skip: int = Field(..., description="Number of templates skipped")
    limit: int = Field(..., description="Number of templates returned")


class TemplatePreviewRequest(BaseModel):
    """Schema for template preview request"""
    context: Optional[Dict[str, Any]] = Field(default={}, description="Context variables for preview")


class TemplatePreviewResponse(BaseModel):
    """Schema for template preview response"""
    template_id: uuid.UUID = Field(..., description="Template ID")
    rendered_content: str = Field(..., description="Rendered template content")
    context_used: Dict[str, Any] = Field(..., description="Context variables used for rendering")


class TemplateSearchParams(BaseModel):
    """Schema for template search parameters"""
    category: Optional[TemplateCategory] = Field(None, description="Filter by category")
    language: Optional[str] = Field(None, description="Filter by language")
    active_only: Optional[bool] = Field(True, description="Return only active templates")
    search: Optional[str] = Field(None, description="Search term")
    skip: Optional[int] = Field(0, ge=0, description="Number of items to skip")
    limit: Optional[int] = Field(100, ge=1, le=1000, description="Number of items to return")