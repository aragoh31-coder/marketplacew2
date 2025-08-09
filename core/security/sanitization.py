import bleach
from django.core.exceptions import ValidationError
from django.utils.html import escape


class UniversalSanitizer:
    """Comprehensive input sanitization framework"""
    
    ALLOWED_TAGS = ['p', 'br', 'strong', 'em', 'ul', 'ol', 'li']
    ALLOWED_ATTRIBUTES = {
        'a': ['href', 'title'],
        'abbr': ['title'],
        'acronym': ['title'],
    }
    
    @classmethod
    def sanitize_html(cls, content):
        """Sanitize HTML content with strict whitelist"""
        if not content:
            return content
        return bleach.clean(
            content,
            tags=cls.ALLOWED_TAGS,
            attributes=cls.ALLOWED_ATTRIBUTES,
            strip=True
        )
    
    @classmethod
    def sanitize_text(cls, content):
        """Remove all HTML from text fields"""
        if not content:
            return content
        return bleach.clean(content, tags=[], strip=True)
    
    @classmethod
    def sanitize_user_input(cls, data, field_types=None):
        """Sanitize dictionary of user input data"""
        if not isinstance(data, dict):
            return data
        
        field_types = field_types or {}
        sanitized = {}
        
        for key, value in data.items():
            if isinstance(value, str):
                if field_types.get(key) == 'html':
                    sanitized[key] = cls.sanitize_html(value)
                else:
                    sanitized[key] = cls.sanitize_text(value)
            else:
                sanitized[key] = value
        
        return sanitized
