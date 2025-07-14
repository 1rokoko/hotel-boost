"""
Comprehensive input sanitization utilities for XSS and injection prevention

This module provides sanitization functions for various types of user input
including HTML, JavaScript, SQL, file uploads, and other potentially dangerous content.
"""

import re
import html
import json
import mimetypes
from typing import Any, Dict, List, Optional, Set, Union, Tuple
from urllib.parse import urlparse, quote
import structlog

logger = structlog.get_logger(__name__)

# Dangerous HTML tags and attributes
DANGEROUS_TAGS = {
    'script', 'object', 'embed', 'applet', 'meta', 'iframe', 'frame', 'frameset',
    'link', 'style', 'base', 'form', 'input', 'button', 'textarea', 'select',
    'option', 'optgroup', 'fieldset', 'legend', 'label'
}

DANGEROUS_ATTRIBUTES = {
    'onload', 'onerror', 'onclick', 'onmouseover', 'onmouseout', 'onmousedown',
    'onmouseup', 'onkeydown', 'onkeyup', 'onkeypress', 'onfocus', 'onblur',
    'onchange', 'onsubmit', 'onreset', 'onselect', 'onunload', 'onbeforeunload',
    'javascript:', 'vbscript:', 'data:', 'expression', 'behavior'
}

# SQL injection patterns
SQL_INJECTION_PATTERNS = [
    r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE)\b)",
    r"(\b(UNION|OR|AND)\b.*\b(SELECT|INSERT|UPDATE|DELETE)\b)",
    r"(--|#|/\*|\*/)",
    r"(\b(SCRIPT|JAVASCRIPT|VBSCRIPT)\b)",
    r"(\b(CHAR|NCHAR|VARCHAR|NVARCHAR)\s*\(\s*\d+\s*\))",
    r"(\b(CAST|CONVERT|SUBSTRING|ASCII|CHAR_LENGTH)\s*\()",
    r"(\b(WAITFOR|DELAY)\b)",
    r"(\b(XP_|SP_)\w+)",
    r"(\b(INFORMATION_SCHEMA|SYSOBJECTS|SYSCOLUMNS)\b)"
]

# XSS patterns
XSS_PATTERNS = [
    r"<\s*script[^>]*>.*?</\s*script\s*>",
    r"javascript\s*:",
    r"vbscript\s*:",
    r"on\w+\s*=",
    r"<\s*iframe[^>]*>",
    r"<\s*object[^>]*>",
    r"<\s*embed[^>]*>",
    r"<\s*applet[^>]*>",
    r"<\s*meta[^>]*>",
    r"<\s*link[^>]*>",
    r"expression\s*\(",
    r"url\s*\(\s*[\"']?\s*javascript:",
    r"@import",
    r"<\s*style[^>]*>.*?</\s*style\s*>"
]

# File upload security
SAFE_FILE_EXTENSIONS = {
    '.txt', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp',
    '.mp3', '.wav', '.ogg', '.mp4', '.avi', '.mov', '.wmv',
    '.zip', '.rar', '.7z', '.tar', '.gz'
}

DANGEROUS_FILE_EXTENSIONS = {
    '.exe', '.bat', '.cmd', '.com', '.pif', '.scr', '.vbs', '.js',
    '.jar', '.app', '.deb', '.pkg', '.dmg', '.iso', '.msi',
    '.php', '.asp', '.aspx', '.jsp', '.py', '.rb', '.pl', '.sh'
}

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB


class InputSanitizationError(Exception):
    """Exception raised when input sanitization fails"""
    pass


class InputSanitizer:
    """Comprehensive input sanitization utility"""
    
    def __init__(self, strict_mode: bool = False):
        self.strict_mode = strict_mode
        self.sql_pattern = re.compile('|'.join(SQL_INJECTION_PATTERNS), re.IGNORECASE)
        self.xss_pattern = re.compile('|'.join(XSS_PATTERNS), re.IGNORECASE | re.DOTALL)
    
    def sanitize_html(self, text: str, allowed_tags: Optional[Set[str]] = None) -> str:
        """
        Sanitize HTML content to prevent XSS attacks
        
        Args:
            text: HTML text to sanitize
            allowed_tags: Set of allowed HTML tags (default: basic formatting tags)
            
        Returns:
            str: Sanitized HTML text
        """
        if not text:
            return ""
        
        if allowed_tags is None:
            allowed_tags = {'p', 'br', 'strong', 'em', 'u', 'b', 'i', 'ul', 'ol', 'li'}
        
        try:
            # Remove dangerous patterns
            text = self.xss_pattern.sub('', text)
            
            # Parse and clean HTML tags
            cleaned_text = self._clean_html_tags(text, allowed_tags)
            
            # Remove dangerous attributes
            cleaned_text = self._remove_dangerous_attributes(cleaned_text)
            
            # Escape remaining HTML entities
            cleaned_text = html.escape(cleaned_text, quote=False)
            
            logger.debug("HTML sanitization completed", original_length=len(text), cleaned_length=len(cleaned_text))
            
            return cleaned_text
            
        except Exception as e:
            logger.error("HTML sanitization failed", error=str(e))
            if self.strict_mode:
                raise InputSanitizationError(f"HTML sanitization failed: {str(e)}")
            return html.escape(text)
    
    def sanitize_sql_input(self, text: str) -> str:
        """
        Sanitize input to prevent SQL injection
        
        Args:
            text: Text to sanitize
            
        Returns:
            str: Sanitized text
        """
        if not text:
            return ""
        
        try:
            # Check for SQL injection patterns
            if self.sql_pattern.search(text):
                logger.warning("Potential SQL injection detected", text_preview=text[:100])
                
                if self.strict_mode:
                    raise InputSanitizationError("Potential SQL injection detected")
                
                # Remove dangerous SQL keywords
                text = self.sql_pattern.sub('', text)
            
            # Escape single quotes
            text = text.replace("'", "''")
            
            # Remove null bytes
            text = text.replace('\x00', '')
            
            return text
            
        except Exception as e:
            logger.error("SQL sanitization failed", error=str(e))
            if self.strict_mode:
                raise InputSanitizationError(f"SQL sanitization failed: {str(e)}")
            return text.replace("'", "''")
    
    def sanitize_json_input(self, data: Union[str, Dict, List]) -> Union[str, Dict, List]:
        """
        Sanitize JSON input to prevent injection attacks
        
        Args:
            data: JSON data to sanitize
            
        Returns:
            Sanitized JSON data
        """
        try:
            if isinstance(data, str):
                # Parse JSON string
                try:
                    parsed_data = json.loads(data)
                    sanitized_data = self._sanitize_json_recursive(parsed_data)
                    return json.dumps(sanitized_data)
                except json.JSONDecodeError:
                    # If not valid JSON, treat as regular string
                    return self.sanitize_text(data)
            else:
                return self._sanitize_json_recursive(data)
                
        except Exception as e:
            logger.error("JSON sanitization failed", error=str(e))
            if self.strict_mode:
                raise InputSanitizationError(f"JSON sanitization failed: {str(e)}")
            return data
    
    def _sanitize_json_recursive(self, data: Any) -> Any:
        """Recursively sanitize JSON data"""
        if isinstance(data, dict):
            return {
                self.sanitize_text(str(key)): self._sanitize_json_recursive(value)
                for key, value in data.items()
            }
        elif isinstance(data, list):
            return [self._sanitize_json_recursive(item) for item in data]
        elif isinstance(data, str):
            return self.sanitize_text(data)
        else:
            return data
    
    def sanitize_text(self, text: str, max_length: Optional[int] = None) -> str:
        """
        Sanitize general text input
        
        Args:
            text: Text to sanitize
            max_length: Maximum allowed length
            
        Returns:
            str: Sanitized text
        """
        if not text:
            return ""
        
        try:
            # Remove null bytes and control characters
            text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
            
            # Normalize whitespace
            text = re.sub(r'\s+', ' ', text).strip()
            
            # Remove potential XSS patterns
            text = self.xss_pattern.sub('', text)
            
            # Truncate if necessary
            if max_length and len(text) > max_length:
                text = text[:max_length]
                logger.warning("Text truncated due to length limit", max_length=max_length)
            
            return text
            
        except Exception as e:
            logger.error("Text sanitization failed", error=str(e))
            if self.strict_mode:
                raise InputSanitizationError(f"Text sanitization failed: {str(e)}")
            return text
    
    def sanitize_phone_number(self, phone: str) -> str:
        """
        Sanitize and validate phone number
        
        Args:
            phone: Phone number to sanitize
            
        Returns:
            str: Sanitized phone number
        """
        if not phone:
            return ""
        
        try:
            # Remove all non-digit characters except +
            cleaned = re.sub(r'[^\d+]', '', phone)
            
            # Validate format
            if not re.match(r'^\+?[1-9]\d{1,14}$', cleaned):
                if self.strict_mode:
                    raise InputSanitizationError("Invalid phone number format")
                logger.warning("Invalid phone number format", phone=phone)
                return ""
            
            # Ensure it starts with +
            if not cleaned.startswith('+'):
                cleaned = '+' + cleaned
            
            return cleaned
            
        except Exception as e:
            logger.error("Phone number sanitization failed", error=str(e))
            if self.strict_mode:
                raise InputSanitizationError(f"Phone sanitization failed: {str(e)}")
            return ""
    
    def sanitize_email(self, email: str) -> str:
        """
        Sanitize and validate email address
        
        Args:
            email: Email address to sanitize
            
        Returns:
            str: Sanitized email address
        """
        if not email:
            return ""
        
        try:
            # Convert to lowercase and strip whitespace
            email = email.lower().strip()
            
            # Basic email validation
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, email):
                if self.strict_mode:
                    raise InputSanitizationError("Invalid email format")
                logger.warning("Invalid email format", email=email)
                return ""
            
            # Check for dangerous characters
            if any(char in email for char in ['<', '>', '"', "'", '&']):
                if self.strict_mode:
                    raise InputSanitizationError("Email contains dangerous characters")
                logger.warning("Email contains dangerous characters", email=email)
                return ""
            
            return email
            
        except Exception as e:
            logger.error("Email sanitization failed", error=str(e))
            if self.strict_mode:
                raise InputSanitizationError(f"Email sanitization failed: {str(e)}")
            return ""
    
    def sanitize_url(self, url: str) -> str:
        """
        Sanitize and validate URL
        
        Args:
            url: URL to sanitize
            
        Returns:
            str: Sanitized URL
        """
        if not url:
            return ""
        
        try:
            # Parse URL
            parsed = urlparse(url)
            
            # Check for dangerous schemes
            if parsed.scheme.lower() in ['javascript', 'vbscript', 'data', 'file']:
                if self.strict_mode:
                    raise InputSanitizationError("Dangerous URL scheme")
                logger.warning("Dangerous URL scheme detected", url=url)
                return ""
            
            # Ensure safe scheme
            if parsed.scheme.lower() not in ['http', 'https', 'ftp', 'ftps']:
                if self.strict_mode:
                    raise InputSanitizationError("Invalid URL scheme")
                return ""
            
            # URL encode dangerous characters
            sanitized_url = quote(url, safe=':/?#[]@!$&\'()*+,;=')
            
            return sanitized_url
            
        except Exception as e:
            logger.error("URL sanitization failed", error=str(e))
            if self.strict_mode:
                raise InputSanitizationError(f"URL sanitization failed: {str(e)}")
            return ""
    
    def _clean_html_tags(self, text: str, allowed_tags: Set[str]) -> str:
        """Remove or escape dangerous HTML tags"""
        # Simple tag removal - in production, use a proper HTML parser like BeautifulSoup
        tag_pattern = r'<\s*(/?)(\w+)([^>]*)>'
        
        def replace_tag(match):
            closing, tag_name, attributes = match.groups()
            tag_name = tag_name.lower()
            
            if tag_name in DANGEROUS_TAGS or tag_name not in allowed_tags:
                return ''  # Remove dangerous or disallowed tags
            
            return match.group(0)  # Keep allowed tags
        
        return re.sub(tag_pattern, replace_tag, text, flags=re.IGNORECASE)
    
    def _remove_dangerous_attributes(self, text: str) -> str:
        """Remove dangerous HTML attributes"""
        for attr in DANGEROUS_ATTRIBUTES:
            # Remove attribute patterns
            pattern = rf'\b{re.escape(attr)}\s*=\s*["\'][^"\']*["\']'
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        return text


# Global sanitizer instance
default_sanitizer = InputSanitizer()

# Convenience functions
def sanitize_html(text: str, allowed_tags: Optional[Set[str]] = None) -> str:
    """Sanitize HTML using default sanitizer"""
    return default_sanitizer.sanitize_html(text, allowed_tags)

def sanitize_text(text: str, max_length: Optional[int] = None) -> str:
    """Sanitize text using default sanitizer"""
    return default_sanitizer.sanitize_text(text, max_length)

def sanitize_phone(phone: str) -> str:
    """Sanitize phone number using default sanitizer"""
    return default_sanitizer.sanitize_phone_number(phone)

def sanitize_email(email: str) -> str:
    """Sanitize email using default sanitizer"""
    return default_sanitizer.sanitize_email(email)

def sanitize_url(url: str) -> str:
    """Sanitize URL using default sanitizer"""
    return default_sanitizer.sanitize_url(url)


# Export main classes and functions
__all__ = [
    'InputSanitizer',
    'InputSanitizationError',
    'sanitize_html',
    'sanitize_text',
    'sanitize_phone',
    'sanitize_email',
    'sanitize_url',
    'default_sanitizer'
]
