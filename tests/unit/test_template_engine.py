"""
Unit tests for template engine
"""

import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.template_engine import TemplateEngine, TemplateEngineError, TemplateNotFoundError
from app.models.message_template import MessageTemplate, TemplateCategory
from app.utils.template_renderer import TemplateRenderer


@pytest.fixture
def mock_db_session():
    """Mock database session"""
    session = AsyncMock(spec=AsyncSession)
    return session


@pytest.fixture
def template_engine(mock_db_session):
    """Template engine instance with mocked dependencies"""
    return TemplateEngine(mock_db_session)


@pytest.fixture
def sample_template():
    """Sample template for testing"""
    return MessageTemplate(
        id=uuid.uuid4(),
        hotel_id=uuid.uuid4(),
        name="Welcome Template",
        category=TemplateCategory.WELCOME,
        content="Hello {{guest_name}}, welcome to {{hotel_name}}!",
        variables=["guest_name", "hotel_name"],
        language="en",
        is_active=True,
        description="Welcome message template"
    )


class TestTemplateEngine:
    """Test cases for TemplateEngine"""

    @pytest.mark.asyncio
    async def test_get_template_by_id_success(self, template_engine, mock_db_session, sample_template):
        """Test successful template retrieval by ID"""
        # Mock database query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_template
        mock_db_session.execute.return_value = mock_result

        # Test
        result = await template_engine.get_template_by_id(sample_template.id, sample_template.hotel_id)

        # Assertions
        assert result == sample_template
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_template_by_id_not_found(self, template_engine, mock_db_session):
        """Test template not found scenario"""
        # Mock database query returning None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        # Test
        result = await template_engine.get_template_by_id(uuid.uuid4(), uuid.uuid4())

        # Assertions
        assert result is None
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_templates_by_category(self, template_engine, mock_db_session, sample_template):
        """Test retrieving templates by category"""
        # Mock database query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_template]
        mock_db_session.execute.return_value = mock_result

        # Test
        result = await template_engine.get_templates_by_category(
            sample_template.hotel_id, TemplateCategory.WELCOME, "en"
        )

        # Assertions
        assert len(result) == 1
        assert result[0] == sample_template
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_best_template_success(self, template_engine, mock_db_session, sample_template):
        """Test finding best template with preferred language"""
        # Mock get_templates_by_category to return template
        with patch.object(template_engine, 'get_templates_by_category', return_value=[sample_template]):
            result = await template_engine.find_best_template(
                sample_template.hotel_id, TemplateCategory.WELCOME, "en"
            )

        # Assertions
        assert result == sample_template

    @pytest.mark.asyncio
    async def test_find_best_template_fallback(self, template_engine, mock_db_session, sample_template):
        """Test finding best template with fallback language"""
        # Mock get_templates_by_category to return empty for preferred, template for fallback
        with patch.object(template_engine, 'get_templates_by_category') as mock_get:
            mock_get.side_effect = [[], [sample_template]]  # Empty for 'es', template for 'en'

            result = await template_engine.find_best_template(
                sample_template.hotel_id, TemplateCategory.WELCOME, "es", "en"
            )

        # Assertions
        assert result == sample_template
        assert mock_get.call_count == 2

    @pytest.mark.asyncio
    async def test_render_template_success(self, template_engine, mock_db_session, sample_template):
        """Test successful template rendering"""
        # Mock dependencies
        with patch.object(template_engine, 'get_template_by_id', return_value=sample_template), \
             patch.object(template_engine.variable_resolver, 'resolve_context',
                         return_value={'guest_name': 'John', 'hotel_name': 'Grand Hotel'}), \
             patch.object(template_engine.renderer, 'render_template_model',
                         return_value='Hello John, welcome to Grand Hotel!'):

            result = await template_engine.render_template(
                sample_template.id, sample_template.hotel_id, {'guest_name': 'John'}
            )

        # Assertions
        assert result == 'Hello John, welcome to Grand Hotel!'

    @pytest.mark.asyncio
    async def test_render_template_not_found(self, template_engine, mock_db_session):
        """Test template rendering when template not found"""
        # Mock get_template_by_id to return None
        with patch.object(template_engine, 'get_template_by_id', return_value=None):
            with pytest.raises(TemplateNotFoundError):
                await template_engine.render_template(uuid.uuid4(), uuid.uuid4(), {})

    @pytest.mark.asyncio
    async def test_render_template_by_category_success(self, template_engine, mock_db_session, sample_template):
        """Test successful template rendering by category"""
        # Mock dependencies
        with patch.object(template_engine, 'find_best_template', return_value=sample_template), \
             patch.object(template_engine.variable_resolver, 'resolve_context',
                         return_value={'guest_name': 'John', 'hotel_name': 'Grand Hotel'}), \
             patch.object(template_engine.renderer, 'render_template_model',
                         return_value='Hello John, welcome to Grand Hotel!'):

            result = await template_engine.render_template_by_category(
                sample_template.hotel_id, TemplateCategory.WELCOME, {'guest_name': 'John'}
            )

        # Assertions
        assert result == 'Hello John, welcome to Grand Hotel!'

    @pytest.mark.asyncio
    async def test_preview_template_success(self, template_engine, mock_db_session, sample_template):
        """Test successful template preview"""
        # Mock dependencies
        with patch.object(template_engine, 'get_template_by_id', return_value=sample_template), \
             patch.object(template_engine.renderer, 'render_template',
                         return_value='Hello John, welcome to Grand Hotel!'):

            result = await template_engine.preview_template(
                sample_template.id, sample_template.hotel_id, {'guest_name': 'John', 'hotel_name': 'Grand Hotel'}
            )

        # Assertions
        assert result == 'Hello John, welcome to Grand Hotel!'