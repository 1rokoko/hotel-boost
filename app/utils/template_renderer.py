"""
Template renderer for WhatsApp Hotel Bot application
"""

import re
from typing import Dict, Any, List, Optional, Set, Union, TYPE_CHECKING
from datetime import datetime
from jinja2 import Environment, BaseLoader, TemplateSyntaxError, UndefinedError, select_autoescape
from jinja2.sandbox import SandboxedEnvironment
import structlog
import hashlib
import json

from app.core.logging import get_logger
from app.schemas.trigger_config import TriggerTemplateVariable, TriggerTemplateValidation

if TYPE_CHECKING:
    from app.models.message_template import MessageTemplate

logger = get_logger(__name__)


class TemplateRendererError(Exception):
    """Base exception for template renderer errors"""
    pass


class TemplateValidationError(TemplateRendererError):
    """Raised when template validation fails"""
    pass


class TemplateRenderingError(TemplateRendererError):
    """Raised when template rendering fails"""
    pass


class TemplateRenderer:
    """Renders Jinja2 templates with security sandboxing and caching"""

    def __init__(self, cache_enabled: bool = True, cache_ttl: int = 3600):
        """
        Initialize template renderer with sandboxed environment

        Args:
            cache_enabled: Whether to enable template caching
            cache_ttl: Cache time-to-live in seconds
        """
        self.logger = logger.bind(service="template_renderer")
        self.cache_enabled = cache_enabled
        self.cache_ttl = cache_ttl
        self._template_cache: Dict[str, Dict[str, Any]] = {}
        self._rendered_cache: Dict[str, Dict[str, Any]] = {}

        # Create sandboxed Jinja2 environment for security
        self.env = SandboxedEnvironment(
            loader=BaseLoader(),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )

        # Add custom filters
        self._add_custom_filters()
    
    def _add_custom_filters(self):
        """Add custom Jinja2 filters for hotel bot use cases"""
        
        def format_phone(phone_number: str) -> str:
            """Format phone number for display"""
            if not phone_number:
                return ""
            # Remove non-digits
            digits = re.sub(r'\D', '', phone_number)
            if len(digits) >= 10:
                return f"+{digits}"
            return phone_number
        
        def format_datetime(dt: datetime, format_str: str = "%Y-%m-%d %H:%M") -> str:
            """Format datetime for display"""
            if not dt:
                return ""
            if isinstance(dt, str):
                try:
                    dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
                except ValueError:
                    return dt
            return dt.strftime(format_str)
        
        def capitalize_name(name: str) -> str:
            """Capitalize name properly"""
            if not name:
                return "Guest"
            return " ".join(word.capitalize() for word in name.split())
        
        def truncate_text(text: str, length: int = 100) -> str:
            """Truncate text to specified length"""
            if not text:
                return ""
            if len(text) <= length:
                return text
            return text[:length-3] + "..."
        
        # Register filters
        self.env.filters['format_phone'] = format_phone
        self.env.filters['format_datetime'] = format_datetime
        self.env.filters['capitalize_name'] = capitalize_name
        self.env.filters['truncate'] = truncate_text

    def _generate_cache_key(self, template_string: str, context: Dict[str, Any]) -> str:
        """
        Generate cache key for template and context combination

        Args:
            template_string: Template content
            context: Context variables

        Returns:
            str: Cache key
        """
        # Create a hash of template content and context
        content_hash = hashlib.md5(template_string.encode()).hexdigest()
        context_hash = hashlib.md5(json.dumps(context, sort_keys=True).encode()).hexdigest()
        return f"{content_hash}_{context_hash}"

    def _is_cache_valid(self, cache_entry: Dict[str, Any]) -> bool:
        """
        Check if cache entry is still valid

        Args:
            cache_entry: Cache entry to check

        Returns:
            bool: True if cache is valid
        """
        if not self.cache_enabled:
            return False

        cache_time = cache_entry.get('timestamp', 0)
        current_time = datetime.utcnow().timestamp()
        return (current_time - cache_time) < self.cache_ttl

    def _get_from_cache(self, cache_key: str) -> Optional[str]:
        """
        Get rendered template from cache

        Args:
            cache_key: Cache key

        Returns:
            Optional[str]: Cached rendered template or None
        """
        if not self.cache_enabled:
            return None

        cache_entry = self._rendered_cache.get(cache_key)
        if cache_entry and self._is_cache_valid(cache_entry):
            self.logger.debug("Template cache hit", cache_key=cache_key)
            return cache_entry['content']

        return None

    def _store_in_cache(self, cache_key: str, content: str) -> None:
        """
        Store rendered template in cache

        Args:
            cache_key: Cache key
            content: Rendered content
        """
        if not self.cache_enabled:
            return

        self._rendered_cache[cache_key] = {
            'content': content,
            'timestamp': datetime.utcnow().timestamp()
        }

        # Clean up old cache entries (simple LRU-like cleanup)
        if len(self._rendered_cache) > 1000:  # Max cache size
            oldest_key = min(
                self._rendered_cache.keys(),
                key=lambda k: self._rendered_cache[k]['timestamp']
            )
            del self._rendered_cache[oldest_key]

    def clear_cache(self) -> None:
        """Clear all cached templates"""
        self._template_cache.clear()
        self._rendered_cache.clear()
        self.logger.info("Template cache cleared")

    async def render_template(
        self,
        template_string: str,
        context: Dict[str, Any]
    ) -> str:
        """
        Render template with given context
        
        Args:
            template_string: Jinja2 template string
            context: Context variables for rendering
            
        Returns:
            str: Rendered template
            
        Raises:
            TemplateRenderingError: If rendering fails
        """
        try:
            # Check cache first
            cache_key = self._generate_cache_key(template_string, context)
            cached_result = self._get_from_cache(cache_key)
            if cached_result is not None:
                return cached_result

            # Validate template first
            validation = await self.validate_template(template_string)
            if not validation.is_valid:
                raise TemplateValidationError(
                    f"Template validation failed: {', '.join(validation.errors)}"
                )

            # Create template object
            template = self.env.from_string(template_string)

            # Add safe defaults to context
            safe_context = self._prepare_context(context)
            
            # Render template
            rendered = template.render(**safe_context)

            # Clean up whitespace
            rendered = self._clean_rendered_text(rendered)

            # Store in cache
            self._store_in_cache(cache_key, rendered)

            self.logger.debug(
                "Template rendered successfully",
                template_length=len(template_string),
                rendered_length=len(rendered),
                cache_key=cache_key
            )

            return rendered
            
        except (TemplateSyntaxError, UndefinedError) as e:
            self.logger.error(
                "Template rendering error",
                error=str(e),
                template=template_string[:100]
            )
            raise TemplateRenderingError(f"Template rendering failed: {str(e)}")
        except TemplateValidationError:
            raise
        except Exception as e:
            self.logger.error(
                "Unexpected error rendering template",
                error=str(e),
                template=template_string[:100]
            )
            raise TemplateRenderingError(f"Unexpected error: {str(e)}")

    async def render_template_model(
        self,
        template_model: 'MessageTemplate',
        context: Dict[str, Any]
    ) -> str:
        """
        Render template from database model

        Args:
            template_model: MessageTemplate model instance
            context: Context variables for rendering

        Returns:
            str: Rendered template

        Raises:
            TemplateRenderingError: If rendering fails
        """
        try:
            # Check if template is active
            if not template_model.is_active:
                raise TemplateRenderingError(f"Template '{template_model.name}' is not active")

            # Add template metadata to context
            enhanced_context = context.copy()
            enhanced_context.update({
                '_template_name': template_model.name,
                '_template_category': template_model.category.value,
                '_template_language': template_model.language,
                '_template_id': str(template_model.id)
            })

            # Render the template
            rendered = await self.render_template(template_model.content, enhanced_context)

            # Update usage statistics
            template_model.increment_usage("render")

            self.logger.info(
                "Template model rendered successfully",
                template_id=str(template_model.id),
                template_name=template_model.name,
                category=template_model.category.value,
                language=template_model.language
            )

            return rendered

        except Exception as e:
            self.logger.error(
                "Error rendering template model",
                template_id=str(template_model.id) if template_model else None,
                error=str(e)
            )
            raise

    async def validate_template(self, template_string: str) -> TriggerTemplateValidation:
        """
        Validate template syntax and extract variables
        
        Args:
            template_string: Template string to validate
            
        Returns:
            TriggerTemplateValidation: Validation result
        """
        errors = []
        warnings = []
        variables = []
        
        try:
            # Check basic syntax
            if not template_string or not template_string.strip():
                errors.append("Template cannot be empty")
                return TriggerTemplateValidation(
                    is_valid=False,
                    variables=[],
                    errors=errors,
                    warnings=warnings
                )
            
            # Parse template to check syntax
            try:
                parsed = self.env.parse(template_string)
            except TemplateSyntaxError as e:
                errors.append(f"Syntax error: {str(e)}")
                return TriggerTemplateValidation(
                    is_valid=False,
                    variables=[],
                    errors=errors,
                    warnings=warnings
                )
            
            # Extract variables
            variables = self._extract_template_variables(template_string)
            
            # Check for potentially unsafe patterns
            unsafe_patterns = [
                r'import\s+',
                r'__\w+__',
                r'exec\s*\(',
                r'eval\s*\(',
                r'open\s*\(',
                r'file\s*\(',
            ]
            
            for pattern in unsafe_patterns:
                if re.search(pattern, template_string, re.IGNORECASE):
                    warnings.append(f"Potentially unsafe pattern detected: {pattern}")
            
            # Check template length
            if len(template_string) > 10000:
                warnings.append("Template is very long, consider breaking it down")
            
            # Check for common issues
            if '{{' in template_string and '}}' not in template_string:
                errors.append("Unclosed variable expression")
            
            if '{%' in template_string and '%}' not in template_string:
                errors.append("Unclosed template tag")
            
            is_valid = len(errors) == 0
            
            return TriggerTemplateValidation(
                is_valid=is_valid,
                variables=variables,
                errors=errors,
                warnings=warnings
            )
            
        except Exception as e:
            self.logger.error(
                "Error validating template",
                error=str(e),
                template=template_string[:100]
            )
            return TriggerTemplateValidation(
                is_valid=False,
                variables=[],
                errors=[f"Validation error: {str(e)}"],
                warnings=warnings
            )
    
    def _extract_template_variables(self, template_string: str) -> List[TriggerTemplateVariable]:
        """
        Extract variables from template string
        
        Args:
            template_string: Template string
            
        Returns:
            List[TriggerTemplateVariable]: List of variables found
        """
        variables = []
        variable_names = set()
        
        # Find variable expressions {{ variable }}
        var_pattern = r'\{\{\s*([^}]+)\s*\}\}'
        matches = re.findall(var_pattern, template_string)
        
        for match in matches:
            # Extract base variable name (before filters/attributes)
            var_name = match.split('|')[0].split('.')[0].strip()
            
            if var_name and var_name not in variable_names:
                variable_names.add(var_name)
                
                # Determine variable type based on common patterns
                var_type = "string"
                if var_name.endswith('_at') or var_name.endswith('_time'):
                    var_type = "datetime"
                elif var_name.endswith('_count') or var_name.endswith('_number'):
                    var_type = "number"
                elif var_name.startswith('is_') or var_name.startswith('has_'):
                    var_type = "boolean"
                
                variables.append(TriggerTemplateVariable(
                    name=var_name,
                    type=var_type,
                    required=True,  # Assume required by default
                    description=f"Template variable: {var_name}"
                ))
        
        return variables
    
    def _prepare_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare context with safe defaults
        
        Args:
            context: Original context
            
        Returns:
            Dict[str, Any]: Safe context with defaults
        """
        safe_context = {
            'now': datetime.utcnow(),
            'today': datetime.utcnow().date(),
            **context
        }
        
        # Ensure guest has safe defaults
        if 'guest' not in safe_context:
            safe_context['guest'] = {}
        
        guest = safe_context['guest']
        if not isinstance(guest, dict):
            guest = {}
        
        guest.setdefault('name', 'Guest')
        guest.setdefault('phone_number', '')
        guest.setdefault('preferences', {})
        
        safe_context['guest'] = guest
        
        # Ensure hotel has safe defaults
        if 'hotel' not in safe_context:
            safe_context['hotel'] = {}
        
        hotel = safe_context['hotel']
        if not isinstance(hotel, dict):
            hotel = {}
        
        hotel.setdefault('name', 'Hotel')
        hotel.setdefault('settings', {})
        
        safe_context['hotel'] = hotel
        
        return safe_context
    
    def _clean_rendered_text(self, text: str) -> str:
        """
        Clean up rendered text
        
        Args:
            text: Rendered text
            
        Returns:
            str: Cleaned text
        """
        # Remove excessive whitespace
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        
        # Trim leading/trailing whitespace
        text = text.strip()
        
        return text


# Export renderer and exceptions
__all__ = [
    'TemplateRenderer',
    'TemplateRendererError',
    'TemplateValidationError',
    'TemplateRenderingError'
]
