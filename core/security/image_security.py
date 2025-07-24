import os
import hashlib
import secrets
from PIL import Image, ImageFilter
from io import BytesIO
import re
from pathlib import Path
from django.conf import settings
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False
    logger.warning("python-magic not available, using basic file validation")
    
    def from_buffer(data, mime=True):
        """Basic MIME type detection without python-magic"""
        if data.startswith(b'\xff\xd8\xff'):
            return 'image/jpeg'
        elif data.startswith(b'\x89PNG\r\n\x1a\n'):
            return 'image/png'
        elif data.startswith(b'GIF87a') or data.startswith(b'GIF89a'):
            return 'image/gif'
        else:
            return 'application/octet-stream'
    
    class MockMagic:
        @staticmethod
        def from_buffer(data, mime=True):
            return from_buffer(data, mime)
    
    magic = MockMagic()

try:
    import paramiko
    PARAMIKO_AVAILABLE = True
except ImportError:
    PARAMIKO_AVAILABLE = False
    logger.warning("paramiko not available, remote storage disabled")

class SecureImageProcessor:
    """
    Ultra-secure image processor for Tor marketplace
    - Validates file types using magic numbers
    - Strips all metadata
    - Re-encodes images to remove exploits
    - Generates secure filenames
    - Supports remote storage
    """
    
    def __init__(self):
        self.config = settings.IMAGE_UPLOAD_SETTINGS
        self.allowed_extensions = self.config['ALLOWED_EXTENSIONS']
        self.allowed_mimetypes = self.config['ALLOWED_MIMETYPES']
        self.max_size = self.config['MAX_FILE_SIZE']
        self.max_dimensions = self.config['MAX_IMAGE_DIMENSIONS']
    
    def validate_and_process_image(self, uploaded_file, user):
        """
        Main entry point for secure image processing
        Returns: (success, filename_or_error, thumbnail_filename)
        """
        try:
            if not self._check_rate_limit(user):
                return False, "Upload rate limit exceeded. Try again later.", None
            
            self._validate_file_size(uploaded_file)
            
            file_content = uploaded_file.read()
            uploaded_file.seek(0)
            
            if not self._validate_magic_numbers(file_content):
                return False, "Invalid file type detected", None
            
            if self._detect_malicious_content(file_content):
                return False, "Suspicious content detected", None
            
            processed_image, thumbnail = self._process_image(file_content)
            
            if not processed_image:
                return False, "Failed to process image", None
            
            filename = self._generate_secure_filename(uploaded_file.name)
            thumb_filename = f"thumb_{filename}"
            
            success = self._save_images(
                processed_image, 
                thumbnail, 
                filename, 
                thumb_filename,
                user
            )
            
            if not success:
                return False, "Failed to save image", None
            
            self._log_upload(user, filename)
            
            return True, filename, thumb_filename
            
        except ValidationError as e:
            return False, str(e), None
        except Exception as e:
            logger.error(f"Image processing error: {str(e)}")
            return False, "Image processing failed", None
    
    def _validate_file_size(self, uploaded_file):
        """Check file size"""
        if uploaded_file.size > self.max_size:
            raise ValidationError(
                f"File too large. Maximum size is {self.max_size // 1024 // 1024}MB"
            )
    
    def _validate_magic_numbers(self, file_content):
        """Validate file type using magic numbers"""
        if MAGIC_AVAILABLE:
            file_mime = magic.from_buffer(file_content, mime=True)
        else:
            file_mime = magic.from_buffer(file_content, mime=True)
        
        if file_mime not in self.allowed_mimetypes:
            logger.warning(f"Invalid MIME type detected: {file_mime}")
            return False
        
        if file_mime == 'image/jpeg':
            if not (file_content[:3] == b'\xff\xd8\xff'):
                return False
        elif file_mime == 'image/png':
            if not (file_content[:8] == b'\x89PNG\r\n\x1a\n'):
                return False
        elif file_mime == 'image/gif':
            if not (file_content[:6] in [b'GIF87a', b'GIF89a']):
                return False
        
        return True
    
    def _detect_malicious_content(self, file_content):
        """Scan for malicious patterns"""
        scan_start = file_content[:1024].lower()
        scan_end = file_content[-1024:].lower() if len(file_content) > 1024 else b''
        
        suspicious_patterns = [
            b'<?php',
            b'<script',
            b'javascript:',
            b'onerror=',
            b'eval(',
            b'exec(',
            b'system(',
            b'shell_exec',
            b'<iframe',
            b'.exe',
            b'.sh',
            b'.bat',
            b'cmd.exe',
            b'/bin/bash',
            b'<html',
            b'<body',
        ]
        
        for pattern in suspicious_patterns:
            if pattern in scan_start or pattern in scan_end:
                logger.warning(f"Malicious pattern detected: {pattern}")
                return True
        
        script_indicators = [b'script', b'javascript', b'eval', b'function', b'var ', b'document']
        script_count = sum(1 for indicator in script_indicators 
                          if indicator in scan_start or indicator in scan_end)
        
        if script_count >= 2:  # Multiple script indicators suggest embedded code
            logger.warning(f"Multiple script indicators detected: {script_count}")
            return True
        
        return False
    
    def _process_image(self, file_content):
        """Process image and convert to JPEG"""
        try:
            img = Image.open(BytesIO(file_content))
            
            img.verify()
            img = Image.open(BytesIO(file_content))  # Reopen after verify
            
            if img.width > self.max_dimensions[0] or img.height > self.max_dimensions[1]:
                ratio = min(
                    self.max_dimensions[0] / img.width,
                    self.max_dimensions[1] / img.height
                )
                new_size = (int(img.width * ratio), int(img.height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            if img.mode != 'RGB':
                if img.mode == 'RGBA':
                    # Create white background
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[3])
                    img = background
                else:
                    img = img.convert('RGB')
            
            img = img.filter(ImageFilter.GaussianBlur(radius=0.1))
            
            thumbnail = img.copy()
            thumbnail.thumbnail(self.config['THUMBNAIL_SIZE'], Image.Resampling.LANCZOS)
            
            output = BytesIO()
            img.save(
                output, 
                format='JPEG', 
                quality=self.config.get('JPEG_QUALITY', 85), 
                optimize=True, 
                progressive=False
            )
            output.seek(0)
            
            if output.getbuffer().nbytes > self.max_size:
                output = BytesIO()
                img.save(
                    output, 
                    format='JPEG', 
                    quality=70,  # Lower quality for smaller size
                    optimize=True
                )
                output.seek(0)
                
                if output.getbuffer().nbytes > self.max_size:
                    img.thumbnail((1280, 720), Image.Resampling.LANCZOS)
                    output = BytesIO()
                    img.save(output, format='JPEG', quality=70, optimize=True)
                    output.seek(0)
            
            thumb_output = BytesIO()
            thumbnail.save(
                thumb_output, 
                format='JPEG', 
                quality=self.config.get('THUMBNAIL_QUALITY', 75), 
                optimize=True
            )
            thumb_output.seek(0)
            
            return output, thumb_output
            
        except Exception as e:
            logger.error(f"PIL processing error: {str(e)}")
            return None, None
    
    def _generate_secure_filename(self, original_filename):
        """Generate cryptographically secure filename - always .jpg"""
        random_name = secrets.token_urlsafe(32)
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        
        filename = f"{timestamp}_{random_name}.jpg"
        
        filename = re.sub(r'[^a-zA-Z0-9._-]', '', filename)
        
        return filename
    
    def _save_images(self, image_data, thumbnail_data, filename, thumb_filename, user):
        """Save images based on storage backend"""
        if self.config['STORAGE_BACKEND'] == 'remote':
            return self._save_to_remote(
                image_data, thumbnail_data, 
                filename, thumb_filename
            )
        else:
            return self._save_locally(
                image_data, thumbnail_data, 
                filename, thumb_filename
            )
    
    def _save_locally(self, image_data, thumbnail_data, filename, thumb_filename):
        """Save to local secure directory"""
        try:
            upload_dir = settings.SECURE_UPLOAD_ROOT / 'products'
            upload_dir.mkdir(parents=True, exist_ok=True)
            
            image_path = upload_dir / filename
            with open(image_path, 'wb') as f:
                f.write(image_data.read())
            
            thumb_path = upload_dir / thumb_filename
            with open(thumb_path, 'wb') as f:
                f.write(thumbnail_data.read())
            
            os.chmod(image_path, 0o644)
            os.chmod(thumb_path, 0o644)
            
            return True
            
        except Exception as e:
            logger.error(f"Local save error: {str(e)}")
            return False
    
    def _save_to_remote(self, image_data, thumbnail_data, filename, thumb_filename):
        """Save to remote read-only server via SFTP"""
        config = self.config['REMOTE_STORAGE_CONFIG']
        
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            if config.get('KEY_PATH'):
                ssh.connect(
                    hostname=config['HOST'],
                    port=config['PORT'],
                    username=config['USERNAME'],
                    key_filename=config['KEY_PATH']
                )
            else:
                ssh.connect(
                    hostname=config['HOST'],
                    port=config['PORT'],
                    username=config['USERNAME'],
                    password=config.get('PASSWORD', '')
                )
            
            sftp = ssh.open_sftp()
            
            remote_path = config['REMOTE_PATH']
            
            with sftp.open(f"{remote_path}/{filename}", 'wb') as f:
                f.write(image_data.read())
            
            with sftp.open(f"{remote_path}/{thumb_filename}", 'wb') as f:
                f.write(thumbnail_data.read())
            
            sftp.close()
            ssh.close()
            
            return True
            
        except Exception as e:
            logger.error(f"Remote save error: {str(e)}")
            return False
    
    def _check_rate_limit(self, user):
        """Check upload rate limits"""
        from django.core.cache import cache
        
        hour_key = f"upload_hour_{user.id}"
        day_key = f"upload_day_{user.id}"
        
        hour_count = cache.get(hour_key, 0)
        day_count = cache.get(day_key, 0)
        
        if hour_count >= self.config['UPLOADS_PER_HOUR']:
            return False
        
        if day_count >= self.config['UPLOADS_PER_DAY']:
            return False
        
        cache.set(hour_key, hour_count + 1, 3600)  # 1 hour
        cache.set(day_key, day_count + 1, 86400)  # 24 hours
        
        return True
    
    def _log_upload(self, user, filename):
        """Log successful upload for security monitoring"""
        logger.info(f"Image upload: user={user.id}, filename={filename}")
    
    def delete_images(self, filename, thumb_filename):
        """Securely delete images"""
        if self.config['STORAGE_BACKEND'] == 'remote':
            pass
        else:
            try:
                upload_dir = settings.SECURE_UPLOAD_ROOT / 'products'
                
                image_path = upload_dir / filename
                if image_path.exists():
                    image_path.unlink()
                
                thumb_path = upload_dir / thumb_filename
                if thumb_path.exists():
                    thumb_path.unlink()
                    
            except Exception as e:
                logger.error(f"Delete error: {str(e)}")
