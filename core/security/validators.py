import re
import html
import bleach
import secrets
from urllib.parse import urlparse
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator, URLValidator
from decimal import Decimal, InvalidOperation
import logging

logger = logging.getLogger(__name__)


class SecureValidator:
    """Enterprise-grade input validation and sanitization"""
    
    # Allowed HTML tags and attributes for rich text (very restrictive)
    ALLOWED_TAGS = ['p', 'br', 'strong', 'em', 'u', 'ol', 'ul', 'li']
    ALLOWED_ATTRIBUTES = {}
    
    # Common XSS patterns
    XSS_PATTERNS = [
        r'<script[^>]*>.*?</script>',
        r'javascript:',
        r'vbscript:',
        r'onload\s*=',
        r'onerror\s*=',
        r'onclick\s*=',
        r'onmouseover\s*=',
        r'onfocus\s*=',
        r'onblur\s*=',
        r'onchange\s*=',
        r'onsubmit\s*=',
        r'<iframe[^>]*>.*?</iframe>',
        r'<object[^>]*>.*?</object>',
        r'<embed[^>]*>.*?</embed>',
        r'<link[^>]*>',
        r'<meta[^>]*>',
        r'<style[^>]*>.*?</style>',
        r'expression\s*\(',
        r'url\s*\(',
        r'@import',
    ]
    
    # SQL injection patterns
    SQL_PATTERNS = [
        r'(\'\s*(or|and)\s*\')',
        r'(\'\s*(union|select|insert|update|delete|drop|create|alter)\s)',
        r'(\s*(union|select|insert|update|delete|drop|create|alter)\s*--)',
        r'(\'\s*;\s*(drop|delete)\s)',
        r'(\/\*.*?\*\/)',
        r'(\'\s*\|\|\s*\')',
        r'(\'\s*\+\s*\')',
        r'(0x[0-9a-f]+)',
        r'(char\s*\(\s*\d+\s*\))',
    ]
    
    # Command injection patterns
    COMMAND_PATTERNS = [
        r'[;&|`$<>]',
        r'\$\(',
        r'`[^`]*`',
        r'\$\{[^}]*\}',
        r'\\x[0-9a-f]{2}',
        r'%[0-9a-f]{2}',
    ]
    
    @classmethod
    def sanitize_html(cls, text, allowed_tags=None, allowed_attributes=None):
        """Sanitize HTML content"""
        if not text:
            return text
        
        if allowed_tags is None:
            allowed_tags = cls.ALLOWED_TAGS
        if allowed_attributes is None:
            allowed_attributes = cls.ALLOWED_ATTRIBUTES
        
        # First pass: remove dangerous patterns
        for pattern in cls.XSS_PATTERNS:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
        
        # Second pass: use bleach for thorough sanitization
        sanitized = bleach.clean(
            text,
            tags=allowed_tags,
            attributes=allowed_attributes,
            strip=True,
            strip_comments=True
        )
        
        return sanitized
    
    @classmethod
    def sanitize_text(cls, text, max_length=None, allow_html=False):
        """Sanitize plain text input"""
        if not text:
            return text
        
        if isinstance(text, bytes):
            text = text.decode('utf-8', errors='ignore')
        
        if not allow_html:
            # Remove all HTML tags
            text = re.sub(r'<[^>]*>', '', text)
            # HTML decode entities
            text = html.unescape(text)
        else:
            text = cls.sanitize_html(text)
        
        # Remove dangerous patterns
        for pattern in cls.XSS_PATTERNS + cls.SQL_PATTERNS + cls.COMMAND_PATTERNS:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Truncate if needed
        if max_length and len(text) > max_length:
            text = text[:max_length].strip()
        
        return text
    
    @classmethod
    def validate_username(cls, username):
        """Validate username with enterprise security requirements"""
        if not username:
            raise ValidationError("Username is required")
        
        username = str(username).strip()
        
        if len(username) < 3:
            raise ValidationError("Username must be at least 3 characters long")
        
        if len(username) > 50:
            raise ValidationError("Username must be less than 50 characters")
        
        # Only allow alphanumeric, underscore, hyphen
        if not re.match(r'^[a-zA-Z0-9_-]+$', username):
            raise ValidationError("Username can only contain letters, numbers, underscores, and hyphens")
        
        # Cannot start or end with special characters
        if username[0] in '_-' or username[-1] in '_-':
            raise ValidationError("Username cannot start or end with underscore or hyphen")
        
        # Cannot contain consecutive special characters
        if re.search(r'[_-]{2,}', username):
            raise ValidationError("Username cannot contain consecutive underscores or hyphens")
        
        # Block common admin/system usernames
        blocked_usernames = [
            'admin', 'administrator', 'root', 'system', 'test', 'user',
            'guest', 'anonymous', 'null', 'undefined', 'api', 'support',
            'help', 'info', 'contact', 'service', 'operator', 'moderator',
            'vendor', 'seller', 'buyer', 'marketplace', 'bitcoin', 'btc',
            'monero', 'xmr', 'crypto', 'wallet', 'escrow', 'security'
        ]
        
        if username.lower() in blocked_usernames:
            raise ValidationError("This username is not allowed")
        
        return username
    
    @classmethod
    def validate_password(cls, password):
        """Enterprise-grade password validation"""
        if not password:
            raise ValidationError("Password is required")
        
        if len(password) < 12:
            raise ValidationError("Password must be at least 12 characters long")
        
        if len(password) > 128:
            raise ValidationError("Password must be less than 128 characters")
        
        # Check for character diversity
        has_upper = re.search(r'[A-Z]', password)
        has_lower = re.search(r'[a-z]', password)
        has_digit = re.search(r'[0-9]', password)
        has_special = re.search(r'[!@#$%^&*()_+=\-\[\]{}|;:,.<>?]', password)
        
        strength_score = sum([bool(has_upper), bool(has_lower), bool(has_digit), bool(has_special)])
        
        if strength_score < 3:
            raise ValidationError("Password must contain at least 3 of the following: uppercase letter, lowercase letter, number, special character")
        
        # Check for common weak patterns
        weak_patterns = [
            r'(.)\1{3,}',  # 4 or more repeated characters
            r'(012|123|234|345|456|567|678|789|890)',  # Sequential numbers
            r'(abc|bcd|cde|def|efg|fgh|ghi|hij|ijk|jkl|klm|lmn|mno|nop|opq|pqr|qrs|rst|stu|tuv|uvw|vwx|wxy|xyz)',  # Sequential letters
            r'(password|admin|login|user|test|guest|qwerty|asdfgh|zxcvbn)',  # Common weak words
        ]
        
        for pattern in weak_patterns:
            if re.search(pattern, password.lower()):
                raise ValidationError("Password contains weak patterns")
        
        return password
    
    @classmethod
    def validate_email(cls, email):
        """Validate email address"""
        if not email:
            return None
        
        email = str(email).strip().lower()
        
        # Use Django's built-in email validator
        validator = EmailValidator()
        try:
            validator(email)
        except ValidationError:
            raise ValidationError("Invalid email address format")
        
        # Additional security checks
        if len(email) > 254:
            raise ValidationError("Email address is too long")
        
        # Block obviously fake domains
        blocked_domains = [
            'test.com', 'example.com', 'localhost', '127.0.0.1',
            'tempmail.org', '10minutemail.com', 'guerrillamail.com'
        ]
        
        domain = email.split('@')[1] if '@' in email else ''
        if domain in blocked_domains:
            raise ValidationError("Email domain is not allowed")
        
        return email
    
    @classmethod
    def validate_crypto_address(cls, address, currency):
        """Validate cryptocurrency addresses"""
        if not address:
            raise ValidationError("Address is required")
        
        address = str(address).strip()
        
        if currency.lower() == 'btc':
            return cls._validate_bitcoin_address(address)
        elif currency.lower() == 'xmr':
            return cls._validate_monero_address(address)
        else:
            raise ValidationError(f"Unsupported currency: {currency}")
    
    @classmethod
    def _validate_bitcoin_address(cls, address):
        """Validate Bitcoin address format"""
        # Legacy P2PKH (starts with 1)
        if re.match(r'^[1][a-km-zA-HJ-NP-Z1-9]{25,34}$', address):
            return address
        
        # P2SH (starts with 3)
        if re.match(r'^[3][a-km-zA-HJ-NP-Z1-9]{25,34}$', address):
            return address
        
        # Bech32 (starts with bc1)
        if re.match(r'^bc1[a-z0-9]{39,59}$', address.lower()):
            return address.lower()
        
        # Testnet addresses
        if re.match(r'^[mn2][a-km-zA-HJ-NP-Z1-9]{25,34}$', address):
            return address
        
        # Testnet Bech32 (starts with tb1)
        if re.match(r'^tb1[a-z0-9]{39,59}$', address.lower()):
            return address.lower()
        
        raise ValidationError("Invalid Bitcoin address format")
    
    @classmethod
    def _validate_monero_address(cls, address):
        """Validate Monero address format"""
        # Standard address (starts with 4)
        if re.match(r'^[48][0-9AB][1-9A-HJ-NP-Za-km-z]{93}$', address):
            return address
        
        # Integrated address (starts with 4)
        if re.match(r'^[48][0-9AB][1-9A-HJ-NP-Za-km-z]{104}$', address):
            return address
        
        # Subaddress (starts with 8)
        if re.match(r'^[8][0-9AB][1-9A-HJ-NP-Za-km-z]{93}$', address):
            return address
        
        # Testnet addresses (starts with 9, A, B)
        if re.match(r'^[9AB][0-9AB][1-9A-HJ-NP-Za-km-z]{93}$', address):
            return address
        
        raise ValidationError("Invalid Monero address format")
    
    @classmethod
    def validate_decimal_amount(cls, amount, currency, min_amount=None, max_amount=None):
        """Validate cryptocurrency amounts"""
        if not amount:
            raise ValidationError("Amount is required")
        
        try:
            if isinstance(amount, str):
                amount = Decimal(amount)
            elif not isinstance(amount, Decimal):
                amount = Decimal(str(amount))
        except (InvalidOperation, ValueError):
            raise ValidationError("Invalid amount format")
        
        if amount <= 0:
            raise ValidationError("Amount must be greater than 0")
        
        # Currency-specific validation
        if currency.lower() == 'btc':
            if amount > Decimal('21000000'):
                raise ValidationError("Amount exceeds maximum possible Bitcoin supply")
            
            # Check for dust (minimum transaction amount)
            if amount < Decimal('0.00000546'):  # 546 satoshis
                raise ValidationError("Amount is below Bitcoin dust threshold")
        
        elif currency.lower() == 'xmr':
            if amount > Decimal('18400000'):  # Approximate max Monero supply
                raise ValidationError("Amount exceeds reasonable Monero supply")
            
            # Monero has 12 decimal places
            if amount < Decimal('0.000000000001'):
                raise ValidationError("Amount is below Monero minimum precision")
        
        # Check custom limits
        if min_amount and amount < min_amount:
            raise ValidationError(f"Amount must be at least {min_amount}")
        
        if max_amount and amount > max_amount:
            raise ValidationError(f"Amount must not exceed {max_amount}")
        
        return amount
    
    @classmethod
    def validate_url(cls, url, allowed_schemes=['http', 'https']):
        """Validate URL with security checks"""
        if not url:
            return None
        
        url = str(url).strip()
        
        # Use Django's URL validator
        validator = URLValidator(schemes=allowed_schemes)
        try:
            validator(url)
        except ValidationError:
            raise ValidationError("Invalid URL format")
        
        # Parse and validate components
        parsed = urlparse(url)
        
        # Block internal/private networks
        blocked_hosts = [
            'localhost', '127.0.0.1', '0.0.0.0', '::1',
            '192.168.', '10.', '172.16.', '172.17.',
            '172.18.', '172.19.', '172.20.', '172.21.',
            '172.22.', '172.23.', '172.24.', '172.25.',
            '172.26.', '172.27.', '172.28.', '172.29.',
            '172.30.', '172.31.', '169.254.'
        ]
        
        hostname = parsed.hostname or ''
        for blocked in blocked_hosts:
            if hostname.startswith(blocked):
                raise ValidationError("URL points to internal network")
        
        return url
    
    @classmethod
    def validate_file_upload(cls, uploaded_file, allowed_types=None, max_size=None):
        """Validate file uploads with security checks"""
        if not uploaded_file:
            return None
        
        # Check file size
        if max_size and uploaded_file.size > max_size:
            raise ValidationError(f"File size exceeds maximum allowed size of {max_size} bytes")
        
        # Check file extension
        if allowed_types:
            file_ext = uploaded_file.name.lower().split('.')[-1] if '.' in uploaded_file.name else ''
            if file_ext not in allowed_types:
                raise ValidationError(f"File type '{file_ext}' is not allowed")
        
        # Check for double extensions
        if uploaded_file.name.count('.') > 1:
            raise ValidationError("Files with multiple extensions are not allowed")
        
        # Basic magic number check
        uploaded_file.seek(0)
        header = uploaded_file.read(1024)
        uploaded_file.seek(0)
        
        # Check for executable files
        if header.startswith(b'\x4d\x5a'):  # PE executable
            raise ValidationError("Executable files are not allowed")
        
        if header.startswith(b'\x7fELF'):  # ELF executable
            raise ValidationError("Executable files are not allowed")
        
        return uploaded_file
    
    @classmethod
    def sanitize_filename(cls, filename):
        """Sanitize filename for secure storage"""
        if not filename:
            return secrets.token_urlsafe(16) + '.bin'
        
        # Remove path separators
        filename = filename.replace('/', '').replace('\\', '')
        
        # Remove dangerous characters
        filename = re.sub(r'[<>:"|?*]', '', filename)
        
        # Remove control characters
        filename = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', filename)
        
        # Limit length
        if len(filename) > 100:
            name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
            filename = name[:90] + ('.' + ext if ext else '')
        
        # Ensure it doesn't start with a dot or dash
        if filename.startswith('.') or filename.startswith('-'):
            filename = 'file_' + filename
        
        return filename or (secrets.token_urlsafe(16) + '.bin')


# Singleton instance
SECURE_VALIDATOR = SecureValidator()