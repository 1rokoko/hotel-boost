"""
Template API endpoints for WhatsApp Hotel Bot
"""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import structlog

from app.database import get_db
from app.services.template_engine import TemplateEngine, TemplateEngineError, TemplateNotFoundError
from app.models.message_template import MessageTemplate, TemplateCategory
from app.schemas.template import (
    TemplateCreate,
    TemplateUpdate,
    TemplateResponse,
    TemplateListResponse,
    TemplatePreviewRequest,
    TemplatePreviewResponse,
    TemplateSearchParams
)
from app.middleware.tenant import get_current_tenant_id

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.post("/", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
def create_template(
    template_data: TemplateCreate,
    db: Session = Depends(get_db),
    hotel_id: uuid.UUID = Depends(get_current_tenant_id)
):
    """
    Create a new message template

    Creates a new message template for the hotel. Templates support Jinja2 syntax
    for variable substitution and can be categorized for easy organization.
    """
    try:
        # Create template instance
        template = MessageTemplate(
            hotel_id=hotel_id,
            name=template_data.name,
            category=template_data.category,
            content=template_data.content,
            variables=template_data.variables or [],
            language=template_data.language or "en",
            description=template_data.description,
            is_active=template_data.is_active if template_data.is_active is not None else True
        )

        # Validate template content
        validation_errors = template.validate_content()
        if validation_errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Template validation failed: {', '.join(validation_errors)}"
            )

        # Save to database
        db.add(template)
        db.commit()
        db.refresh(template)

        logger.info(
            "Template created successfully",
            template_id=str(template.id),
            hotel_id=str(hotel_id),
            template_name=template.name,
            category=template.category.value
        )

        return TemplateResponse.from_orm(template)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Error creating template",
            hotel_id=str(hotel_id),
            template_name=template_data.name,
            error=str(e)
        )
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create template"
        )


@router.get("/", response_model=TemplateListResponse)
def list_templates(
    category: Optional[TemplateCategory] = Query(None, description="Filter by category"),
    language: Optional[str] = Query(None, description="Filter by language"),
    active_only: bool = Query(True, description="Return only active templates"),
    search: Optional[str] = Query(None, description="Search in template names and descriptions"),
    skip: int = Query(0, ge=0, description="Number of templates to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of templates to return"),
    db: Session = Depends(get_db),
    hotel_id: uuid.UUID = Depends(get_current_tenant_id)
):
    """
    List message templates for the hotel

    Returns a paginated list of message templates with optional filtering
    by category, language, and active status.
    """
    try:
        template_engine = TemplateEngine(db)

        # Build query conditions
        conditions = [MessageTemplate.hotel_id == hotel_id]

        if category:
            conditions.append(MessageTemplate.category == category)

        if language:
            conditions.append(MessageTemplate.language == language)

        if active_only:
            conditions.append(MessageTemplate.is_active == True)

        if search:
            search_term = f"%{search}%"
            conditions.append(
                or_(
                    MessageTemplate.name.ilike(search_term),
                    MessageTemplate.description.ilike(search_term)
                )
            )

        # Execute query with pagination
        from sqlalchemy import select, and_, or_, func

        query = select(MessageTemplate).where(and_(*conditions))
        count_query = select(func.count(MessageTemplate.id)).where(and_(*conditions))

        # Get total count
        count_result = db.execute(count_query)
        total = count_result.scalar()

        # Get paginated results
        query = query.offset(skip).limit(limit).order_by(MessageTemplate.created_at.desc())
        result = db.execute(query)
        templates = result.scalars().all()

        logger.debug(
            "Templates listed successfully",
            hotel_id=str(hotel_id),
            total=total,
            returned=len(templates),
            category=category.value if category else None,
            language=language
        )

        return TemplateListResponse(
            templates=[TemplateResponse.from_orm(t) for t in templates],
            total=total,
            skip=skip,
            limit=limit
        )

    except Exception as e:
        logger.error(
            "Error listing templates",
            hotel_id=str(hotel_id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list templates"
        )


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: uuid.UUID = Path(..., description="Template ID"),
    db: Session = Depends(get_db),
    hotel_id: uuid.UUID = Depends(get_current_tenant_id)
):
    """
    Get a specific message template by ID

    Returns the details of a specific message template belonging to the hotel.
    """
    try:
        template_engine = TemplateEngine(db)
        template = await template_engine.get_template_by_id(template_id, hotel_id)

        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found"
            )

        logger.debug(
            "Template retrieved successfully",
            template_id=str(template_id),
            hotel_id=str(hotel_id),
            template_name=template.name
        )

        return TemplateResponse.from_orm(template)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Error retrieving template",
            template_id=str(template_id),
            hotel_id=str(hotel_id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve template"
        )


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: uuid.UUID = Path(..., description="Template ID"),
    template_data: TemplateUpdate = ...,
    db: Session = Depends(get_db),
    hotel_id: uuid.UUID = Depends(get_current_tenant_id)
):
    """
    Update a message template

    Updates an existing message template with the provided data.
    Only provided fields will be updated.
    """
    try:
        template_engine = TemplateEngine(db)
        template = await template_engine.get_template_by_id(template_id, hotel_id)

        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found"
            )

        # Update fields if provided
        update_data = template_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(template, field, value)

        # Validate updated template content
        validation_errors = template.validate_content()
        if validation_errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Template validation failed: {', '.join(validation_errors)}"
            )

        # Save changes
        db.commit()
        db.refresh(template)

        logger.info(
            "Template updated successfully",
            template_id=str(template_id),
            hotel_id=str(hotel_id),
            template_name=template.name,
            updated_fields=list(update_data.keys())
        )

        return TemplateResponse.from_orm(template)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Error updating template",
            template_id=str(template_id),
            hotel_id=str(hotel_id),
            error=str(e)
        )
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update template"
        )


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: uuid.UUID = Path(..., description="Template ID"),
    db: Session = Depends(get_db),
    hotel_id: uuid.UUID = Depends(get_current_tenant_id)
):
    """
    Delete a message template

    Permanently deletes a message template. This action cannot be undone.
    """
    try:
        template_engine = TemplateEngine(db)
        template = await template_engine.get_template_by_id(template_id, hotel_id)

        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found"
            )

        # Delete template
        db.delete(template)
        db.commit()

        logger.info(
            "Template deleted successfully",
            template_id=str(template_id),
            hotel_id=str(hotel_id),
            template_name=template.name
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Error deleting template",
            template_id=str(template_id),
            hotel_id=str(hotel_id),
            error=str(e)
        )
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete template"
        )


@router.post("/{template_id}/preview", response_model=TemplatePreviewResponse)
async def preview_template(
    template_id: uuid.UUID = Path(..., description="Template ID"),
    preview_data: TemplatePreviewRequest = ...,
    db: Session = Depends(get_db),
    hotel_id: uuid.UUID = Depends(get_current_tenant_id)
):
    """
    Preview a message template with sample data

    Renders the template with provided sample data to show how it will look
    when sent to guests. This is useful for testing templates before activation.
    """
    try:
        template_engine = TemplateEngine(db)

        # Preview template with provided context
        rendered_content = await template_engine.preview_template(
            template_id, hotel_id, preview_data.context
        )

        logger.debug(
            "Template preview generated",
            template_id=str(template_id),
            hotel_id=str(hotel_id),
            context_keys=list(preview_data.context.keys()) if preview_data.context else []
        )

        return TemplatePreviewResponse(
            template_id=template_id,
            rendered_content=rendered_content,
            context_used=preview_data.context or {}
        )

    except TemplateNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    except TemplateEngineError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Template rendering failed: {str(e)}"
        )
    except Exception as e:
        logger.error(
            "Error generating template preview",
            template_id=str(template_id),
            hotel_id=str(hotel_id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate template preview"
        )


@router.get("/categories", response_model=List[str])
def get_template_categories():
    """
    Get available template categories

    Returns a list of all available template categories that can be used
    when creating or filtering templates.
    """
    return [category.value for category in TemplateCategory]