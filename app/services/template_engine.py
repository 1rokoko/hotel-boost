"""
Template engine service for WhatsApp Hotel Bot application
"""

import uuid
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
import structlog

from app.models.message_template import MessageTemplate, TemplateCategory
from app.models.hotel import Hotel
from app.utils.template_renderer import TemplateRenderer, TemplateRenderingError
from app.utils.variable_resolver import VariableResolver
from app.core.logging import get_logger

logger = get_logger(__name__)


class TemplateEngineError(Exception):
    """Base exception for template engine errors"""
    pass


class TemplateNotFoundError(TemplateEngineError):
    """Raised when template is not found"""
    pass


class TemplateEngine:
    """
    Template engine service for managing and rendering message templates

    This service orchestrates template selection, variable resolution,
    and rendering for the WhatsApp hotel bot system.
    """

    def __init__(self, db_session: AsyncSession):
        """
        Initialize template engine

        Args:
            db_session: Database session
        """
        self.db = db_session
        self.logger = logger.bind(service="template_engine")
        self.renderer = TemplateRenderer(cache_enabled=True)
        self.variable_resolver = VariableResolver(db_session)

    async def get_template_by_id(
        self,
        template_id: Union[str, uuid.UUID],
        hotel_id: Union[str, uuid.UUID]
    ) -> Optional[MessageTemplate]:
        """
        Get template by ID with hotel validation

        Args:
            template_id: Template ID
            hotel_id: Hotel ID for tenant isolation

        Returns:
            Optional[MessageTemplate]: Template if found and accessible
        """
        try:
            query = select(MessageTemplate).where(
                and_(
                    MessageTemplate.id == template_id,
                    MessageTemplate.hotel_id == hotel_id
                )
            )
            result = await self.db.execute(query)
            template = result.scalar_one_or_none()

            if template:
                self.logger.debug(
                    "Template retrieved by ID",
                    template_id=str(template_id),
                    hotel_id=str(hotel_id),
                    template_name=template.name
                )

            return template

        except Exception as e:
            self.logger.error(
                "Error retrieving template by ID",
                template_id=str(template_id),
                hotel_id=str(hotel_id),
                error=str(e)
            )
            raise TemplateEngineError(f"Failed to retrieve template: {str(e)}")

    async def get_templates_by_category(
        self,
        hotel_id: Union[str, uuid.UUID],
        category: TemplateCategory,
        language: str = "en",
        active_only: bool = True
    ) -> List[MessageTemplate]:
        """
        Get templates by category and language

        Args:
            hotel_id: Hotel ID for tenant isolation
            category: Template category
            language: Language code
            active_only: Whether to return only active templates

        Returns:
            List[MessageTemplate]: List of matching templates
        """
        try:
            conditions = [
                MessageTemplate.hotel_id == hotel_id,
                MessageTemplate.category == category,
                MessageTemplate.language == language
            ]

            if active_only:
                conditions.append(MessageTemplate.is_active == True)

            query = select(MessageTemplate).where(and_(*conditions))
            result = await self.db.execute(query)
            templates = result.scalars().all()

            self.logger.debug(
                "Templates retrieved by category",
                hotel_id=str(hotel_id),
                category=category.value,
                language=language,
                count=len(templates)
            )

            return list(templates)

        except Exception as e:
            self.logger.error(
                "Error retrieving templates by category",
                hotel_id=str(hotel_id),
                category=category.value,
                language=language,
                error=str(e)
            )
            raise TemplateEngineError(f"Failed to retrieve templates: {str(e)}")

    async def find_best_template(
        self,
        hotel_id: Union[str, uuid.UUID],
        category: TemplateCategory,
        language: str = "en",
        fallback_language: str = "en"
    ) -> Optional[MessageTemplate]:
        """
        Find the best template for given criteria with language fallback

        Args:
            hotel_id: Hotel ID for tenant isolation
            category: Template category
            language: Preferred language
            fallback_language: Fallback language if preferred not found

        Returns:
            Optional[MessageTemplate]: Best matching template
        """
        try:
            # First try preferred language
            templates = await self.get_templates_by_category(
                hotel_id, category, language, active_only=True
            )

            if templates:
                # Return the first active template (could add more sophisticated selection)
                return templates[0]

            # Fallback to default language if different
            if language != fallback_language:
                templates = await self.get_templates_by_category(
                    hotel_id, category, fallback_language, active_only=True
                )

                if templates:
                    self.logger.info(
                        "Using fallback language template",
                        hotel_id=str(hotel_id),
                        category=category.value,
                        requested_language=language,
                        fallback_language=fallback_language
                    )
                    return templates[0]

            self.logger.warning(
                "No template found for criteria",
                hotel_id=str(hotel_id),
                category=category.value,
                language=language,
                fallback_language=fallback_language
            )

            return None

        except Exception as e:
            self.logger.error(
                "Error finding best template",
                hotel_id=str(hotel_id),
                category=category.value,
                language=language,
                error=str(e)
            )
            raise TemplateEngineError(f"Failed to find template: {str(e)}")

    async def render_template(
        self,
        template_id: Union[str, uuid.UUID],
        hotel_id: Union[str, uuid.UUID],
        context: Dict[str, Any]
    ) -> str:
        """
        Render template by ID with context

        Args:
            template_id: Template ID
            hotel_id: Hotel ID for tenant isolation
            context: Context variables for rendering

        Returns:
            str: Rendered template

        Raises:
            TemplateNotFoundError: If template not found
            TemplateRenderingError: If rendering fails
        """
        try:
            # Get template
            template = await self.get_template_by_id(template_id, hotel_id)
            if not template:
                raise TemplateNotFoundError(f"Template {template_id} not found for hotel {hotel_id}")

            # Resolve variables
            resolved_context = await self.variable_resolver.resolve_context(
                context, template.get_variable_names(), hotel_id
            )

            # Render template
            rendered = await self.renderer.render_template_model(template, resolved_context)

            self.logger.info(
                "Template rendered successfully",
                template_id=str(template_id),
                hotel_id=str(hotel_id),
                template_name=template.name
            )

            return rendered

        except TemplateNotFoundError:
            raise
        except Exception as e:
            self.logger.error(
                "Error rendering template",
                template_id=str(template_id),
                hotel_id=str(hotel_id),
                error=str(e)
            )
            raise TemplateRenderingError(f"Failed to render template: {str(e)}")

    async def render_template_by_category(
        self,
        hotel_id: Union[str, uuid.UUID],
        category: TemplateCategory,
        context: Dict[str, Any],
        language: str = "en"
    ) -> str:
        """
        Render template by category with automatic template selection

        Args:
            hotel_id: Hotel ID for tenant isolation
            category: Template category
            context: Context variables for rendering
            language: Language preference

        Returns:
            str: Rendered template

        Raises:
            TemplateNotFoundError: If no template found for category
            TemplateRenderingError: If rendering fails
        """
        try:
            # Find best template
            template = await self.find_best_template(hotel_id, category, language)
            if not template:
                raise TemplateNotFoundError(
                    f"No template found for category {category.value} in language {language}"
                )

            # Resolve variables
            resolved_context = await self.variable_resolver.resolve_context(
                context, template.get_variable_names(), hotel_id
            )

            # Render template
            rendered = await self.renderer.render_template_model(template, resolved_context)

            self.logger.info(
                "Template rendered by category",
                hotel_id=str(hotel_id),
                category=category.value,
                language=language,
                template_id=str(template.id),
                template_name=template.name
            )

            return rendered

        except TemplateNotFoundError:
            raise
        except Exception as e:
            self.logger.error(
                "Error rendering template by category",
                hotel_id=str(hotel_id),
                category=category.value,
                language=language,
                error=str(e)
            )
            raise TemplateRenderingError(f"Failed to render template: {str(e)}")

    async def preview_template(
        self,
        template_id: Union[str, uuid.UUID],
        hotel_id: Union[str, uuid.UUID],
        sample_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Preview template with sample data

        Args:
            template_id: Template ID
            hotel_id: Hotel ID for tenant isolation
            sample_context: Sample context data (uses defaults if not provided)

        Returns:
            str: Rendered template preview

        Raises:
            TemplateNotFoundError: If template not found
            TemplateRenderingError: If rendering fails
        """
        try:
            # Get template
            template = await self.get_template_by_id(template_id, hotel_id)
            if not template:
                raise TemplateNotFoundError(f"Template {template_id} not found for hotel {hotel_id}")

            # Use sample context or generate defaults
            if sample_context is None:
                sample_context = await self.variable_resolver.generate_sample_context(
                    template.get_variable_names(), hotel_id
                )

            # Render template (don't update usage stats for preview)
            rendered = await self.renderer.render_template(template.content, sample_context)

            self.logger.debug(
                "Template preview generated",
                template_id=str(template_id),
                hotel_id=str(hotel_id),
                template_name=template.name
            )

            return rendered

        except TemplateNotFoundError:
            raise
        except Exception as e:
            self.logger.error(
                "Error generating template preview",
                template_id=str(template_id),
                hotel_id=str(hotel_id),
                error=str(e)
            )
            raise TemplateRenderingError(f"Failed to preview template: {str(e)}")