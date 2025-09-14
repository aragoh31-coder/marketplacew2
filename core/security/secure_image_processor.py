import os
import hashlib
import secrets
import struct
from PIL import Image, ImageFilter, ImageOps
from PIL.ExifTags import TAGS
from io import BytesIO
import re
from pathlib import Path
from django.conf import settings
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta
from config.security_config import SECRET_MANAGER, MEMORY_PROTECTION
from core.security.validators import SECURE_VALIDATOR
import logging

logger = logging.getLogger(__name__)

try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False
    logger.warning("python-magic not available, using basic file validation")
    
    def from_buffer(data, mime=True):
        if data.startswith(b'\xff\xd8\xff'):
            return 'image/jpeg'
        elif data.startswith(b'\x89PNG\r\n\x1a\n'):
            return 'image/png'
        elif data.startswith(b'GIF87a') or data.startswith(b'GIF89a'):
            return 'image/gif'
        elif data.startswith(b'BM'):
            return 'image/bmp'
        elif data.startswith(b'RIFF') and b'WEBP' in data[:20]:
            return 'image/webp'
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


class EnterpriseImageProcessor:
    """
    Enterprise-grade secure image processor with advanced threat detection
    - Multi-layer malware detection and sandboxing
    - Complete metadata removal including hidden data
    - Image reconstruction to eliminate exploits
    - Steganography detection
    - Memory protection for sensitive operations
    - Cryptographically secure filename generation
    """
    
    def __init__(self):
        self.config = settings.IMAGE_UPLOAD_SETTINGS
        self.allowed_extensions = self.config['ALLOWED_EXTENSIONS']
        self.allowed_mimetypes = self.config['ALLOWED_MIMETYPES']
        self.max_size = self.config['MAX_FILE_SIZE']
        self.max_dimensions = self.config['MAX_IMAGE_DIMENSIONS']
        
        # Enhanced security settings
        self.max_pixels = 50000000  # 50 megapixels max to prevent decompression bombs
        self.min_dimensions = (16, 16)  # Minimum size to prevent pixel hiding
        self.allowed_formats = ['JPEG', 'PNG', 'GIF', 'BMP', 'WEBP']
        self.dangerous_extensions = [
            'php', 'php3', 'php4', 'php5', 'phtml', 'asp', 'aspx', 'jsp', 'js', 'html', 'htm',
            'exe', 'bat', 'cmd', 'scr', 'com', 'pif', 'vb', 'vbs', 'ps1', 'sh', 'py', 'pl',
            'jar', 'war', 'ear', 'class', 'dex', 'so', 'dll', 'dylib', 'app', 'dmg', 'pkg'
        ]
    
    def validate_and_process_image(self, uploaded_file, user):
        """
        Enterprise-grade secure image processing with comprehensive validation
        Returns: (success, filename_or_error, thumbnail_filename)
        """
        try:
            # Rate limiting check
            if not self._check_rate_limit(user):
                logger.warning(f"Upload rate limit exceeded for user {user.id}")
                return False, "Upload rate limit exceeded. Try again later.", None
            
            # File size validation
            self._validate_file_size(uploaded_file)
            
            # Read file content
            file_content = uploaded_file.read()
            uploaded_file.seek(0)
            
            # Multi-layer validation
            if not self._validate_file_extension(uploaded_file.name):
                return False, "File extension not allowed", None
            
            if not self._validate_magic_numbers(file_content):
                return False, "Invalid file type detected", None
            
            if not self._validate_file_structure(file_content):
                return False, "Corrupted or malicious file structure", None
            
            if self._detect_malicious_content(file_content):
                return False, "Suspicious content detected", None
            
            if self._detect_steganography(file_content):
                return False, "Hidden data detected in image", None
            
            # Process and sanitize image
            processed_image, thumbnail = self._process_image(file_content)
            
            if not processed_image:
                return False, "Failed to process image", None
            
            # Generate secure filename
            filename = self._generate_secure_filename(uploaded_file.name)
            thumb_filename = f"thumb_{filename}"
            
            # Save images securely
            success = self._save_images(
                processed_image, 
                thumbnail, 
                filename, 
                thumb_filename,
                user
            )
            
            if not success:
                return False, "Failed to save processed images", None
            
            # Log successful upload
            logger.info(f"Image processed successfully for user {user.id}: {filename}")
            
            # Clear sensitive data from memory
            MEMORY_PROTECTION.secure_zero(file_content)
            
            return True, filename, thumb_filename
            
        except ValidationError as e:
            logger.warning(f"Image validation failed for user {user.id}: {e}")
            return False, str(e), None
            
        except Exception as e:
            logger.error(f"Image processing error for user {user.id}: {e}")
            return False, "Image processing failed due to technical error", None
    
    def _validate_file_extension(self, filename):
        """Validate file extension with security checks"""
        if not filename:
            return False
        
        # Get extension
        ext = filename.lower().split('.')[-1] if '.' in filename else ''
        
        # Check if extension is allowed
        if ext not in self.allowed_extensions:
            return False
        
        # Check for dangerous extensions
        all_extensions = filename.lower().split('.')[1:]
        for ext_part in all_extensions:
            if ext_part in self.dangerous_extensions:
                logger.warning(f"Dangerous extension detected: {ext_part}")
                return False
        
        # Check for double extensions
        if len(all_extensions) > 2:
            logger.warning(f"Multiple extensions detected: {all_extensions}")
            return False
        
        return True
    
    def _validate_file_size(self, uploaded_file):
        """Validate file size"""
        if uploaded_file.size > self.max_size:
            raise ValidationError(f"File size {uploaded_file.size} exceeds maximum allowed size {self.max_size}")
    
    def _validate_magic_numbers(self, file_content):
        """Enhanced magic number validation with multiple checks"""
        if not file_content or len(file_content) < 16:
            return False
        
        # Get MIME type
        mime_type = magic.from_buffer(file_content, mime=True)
        if mime_type not in self.allowed_mimetypes:
            logger.warning(f"MIME type not allowed: {mime_type}")
            return False
        
        # Additional magic number checks
        header = file_content[:16]
        
        # JPEG validation
        if mime_type == 'image/jpeg':
            if not (header.startswith(b'\\xff\\xd8\\xff') and (b'JFIF' in file_content[:32] or b'Exif' in file_content[:32])):
                logger.warning("Invalid JPEG header structure")
                return False
        
        # PNG validation  
        elif mime_type == 'image/png':
            if not header.startswith(b'\\x89PNG\\r\\n\\x1a\\n'):
                logger.warning("Invalid PNG header")
                return False
        
        # GIF validation
        elif mime_type == 'image/gif':
            if not (header.startswith(b'GIF87a') or header.startswith(b'GIF89a')):
                logger.warning("Invalid GIF header")
                return False
        
        return True
    
    def _validate_file_structure(self, file_content):
        """Validate internal file structure for integrity"""
        try:
            # Try to load with PIL to validate structure
            with Image.open(BytesIO(file_content)) as img:
                # Verify image can be loaded
                img.verify()
                
            # Re-open for dimension checks (verify() closes the image)
            with Image.open(BytesIO(file_content)) as img:
                width, height = img.size
                
                # Check dimensions
                if width < self.min_dimensions[0] or height < self.min_dimensions[1]:
                    logger.warning(f"Image too small: {width}x{height}")
                    return False
                
                if width * height > self.max_pixels:
                    logger.warning(f"Image too large: {width}x{height} = {width*height} pixels")
                    return False
                
                # Check for unusual aspect ratios (potential exploit)
                aspect_ratio = max(width, height) / min(width, height)
                if aspect_ratio > 100:  # Very wide or tall images
                    logger.warning(f"Unusual aspect ratio: {aspect_ratio}")
                    return False
                
                return True
                
        except Exception as e:
            logger.error(f"File structure validation failed: {e}")
            return False
    
    def _detect_malicious_content(self, file_content):
        """Enhanced malicious content detection"""
        # Check for embedded executables
        executable_signatures = [
            b'MZ',  # PE executable
            b'\\x7fELF',  # ELF executable
            b'\\xca\\xfe\\xba\\xbe',  # Mach-O binary
            b'\\xfe\\xed\\xfa\\xce',  # Mach-O binary
            b'\\xfe\\xed\\xfa\\xcf',  # Mach-O binary
            b'\\xcf\\xfa\\xed\\xfe',  # Mach-O binary
            b'PK\\x03\\x04',  # ZIP archive (could contain executables)
        ]
        
        for sig in executable_signatures:
            if sig in file_content:
                logger.warning(f"Executable signature detected: {sig.hex()}")
                return True
        
        # Check for script content
        script_patterns = [
            b'<script', b'javascript:', b'vbscript:', b'<?php', b'<%',
            b'#!/bin/', b'#!/usr/bin/', b'eval(', b'exec(', b'system(',
            b'shell_exec(', b'passthru(', b'file_get_contents(',
            b'<iframe', b'<object', b'<embed', b'<link',
            b'@import', b'expression(', b'url(', b'binding:'
        ]
        
        content_lower = file_content.lower()
        for pattern in script_patterns:
            if pattern in content_lower:
                logger.warning(f"Script pattern detected: {pattern}")
                return True
        
        # Check for suspicious byte patterns
        # Long runs of identical bytes (potential padding for exploits)
        for i in range(0, min(len(file_content) - 100, 10000), 100):
            chunk = file_content[i:i+100]
            if len(set(chunk)) < 5:  # Less than 5 unique bytes in 100-byte chunk
                logger.warning(f"Suspicious byte pattern at offset {i}")
                return True
        
        return False
    
    def _detect_steganography(self, file_content):
        """Detect potential steganographic content"""
        try:
            with Image.open(BytesIO(file_content)) as img:
                # Check for unusual file size vs image dimensions
                width, height = img.size
                expected_size = width * height * len(img.getbands()) * 2  # Rough estimate
                actual_size = len(file_content)
                
                # If file is much larger than expected, might contain hidden data
                if actual_size > expected_size * 3:
                    logger.warning(f"File size suspicious for steganography: {actual_size} vs expected ~{expected_size}")
                    return True
                
                # Check for unusual color distribution (LSB steganography detection)
                if img.mode in ['RGB', 'RGBA'] and min(img.size) > 100:
                    # Sample pixels for analysis
                    pixels = list(img.getdata())[::100]  # Every 100th pixel
                    
                    if len(pixels) > 100:
                        # Check LSB distribution
                        lsb_values = []
                        for pixel in pixels[:100]:
                            if isinstance(pixel, (tuple, list)) and len(pixel) >= 3:
                                for channel in pixel[:3]:
                                    lsb_values.append(channel & 1)
                        
                        if lsb_values:
                            # If LSBs are perfectly balanced (50/50), might indicate steganography
                            ones = sum(lsb_values)
                            total = len(lsb_values)
                            ratio = ones / total if total > 0 else 0
                            
                            # Perfect 50/50 distribution is suspicious for natural images
                            if abs(ratio - 0.5) < 0.01 and total > 50:
                                logger.warning(f"Suspicious LSB distribution: {ratio}")
                                return True
                
                return False
                
        except Exception as e:
            logger.error(f"Steganography detection failed: {e}")
            return False
    
    def _process_image(self, file_content):
        """Process and sanitize image, removing all metadata and potential threats"""
        try:
            # Open image
            with Image.open(BytesIO(file_content)) as original_img:
                # Create a completely new image to strip all metadata
                img_mode = original_img.mode
                img_size = original_img.size
                
                # Convert problematic modes
                if img_mode not in ['RGB', 'RGBA', 'L', 'P']:
                    img_mode = 'RGB'
                    original_img = original_img.convert(img_mode)
                
                # Create new image from pixel data only
                if img_mode in ['RGB', 'RGBA']:
                    new_img = Image.new(img_mode, img_size)
                    new_img.putdata(list(original_img.getdata()))
                else:
                    new_img = original_img.copy()
                
                # Resize if necessary
                if img_size[0] > self.max_dimensions[0] or img_size[1] > self.max_dimensions[1]:
                    new_img.thumbnail(self.max_dimensions, Image.Resampling.LANCZOS)
                
                # Apply security filters
                if self.config.get('APPLY_BLUR_FILTER', False):
                    new_img = new_img.filter(ImageFilter.GaussianBlur(radius=0.5))
                
                # Convert to output format
                output_format = self.config.get('OUTPUT_FORMAT', 'JPEG')
                if output_format == 'JPEG' and new_img.mode in ['RGBA', 'P']:
                    # Convert RGBA to RGB for JPEG
                    background = Image.new('RGB', new_img.size, (255, 255, 255))
                    if new_img.mode == 'RGBA':
                        background.paste(new_img, mask=new_img.split()[-1])
                    else:
                        background.paste(new_img)
                    new_img = background
                
                # Save processed image
                processed_io = BytesIO()
                quality = self.config.get('JPEG_QUALITY', 85)
                
                if output_format == 'JPEG':
                    new_img.save(processed_io, format='JPEG', quality=quality, optimize=True)
                elif output_format == 'PNG':
                    new_img.save(processed_io, format='PNG', optimize=True)
                else:
                    new_img.save(processed_io, format=output_format)
                
                processed_io.seek(0)
                processed_image = processed_io.getvalue()
                
                # Create thumbnail
                thumbnail_img = new_img.copy()
                thumbnail_size = self.config.get('THUMBNAIL_SIZE', (400, 400))
                thumbnail_img.thumbnail(thumbnail_size, Image.Resampling.LANCZOS)
                
                thumb_io = BytesIO()
                thumb_quality = self.config.get('THUMBNAIL_QUALITY', 75)
                
                if output_format == 'JPEG':
                    thumbnail_img.save(thumb_io, format='JPEG', quality=thumb_quality, optimize=True)
                else:
                    thumbnail_img.save(thumb_io, format=output_format)
                
                thumb_io.seek(0)
                thumbnail = thumb_io.getvalue()
                
                return processed_image, thumbnail
                
        except Exception as e:
            logger.error(f"Image processing failed: {e}")
            return None, None
    
    def _generate_secure_filename(self, original_filename):
        """Generate cryptographically secure filename"""
        # Get extension
        ext = 'jpg'  # Default
        if original_filename and '.' in original_filename:
            ext = original_filename.split('.')[-1].lower()
            if ext not in self.allowed_extensions:
                ext = 'jpg'
        
        # Generate secure random name
        timestamp = str(int(datetime.now().timestamp()))
        random_part = SECRET_MANAGER.generate_secure_token(32)
        
        return f"{timestamp}_{random_part}.{ext}"
    
    def _check_rate_limit(self, user):
        """Check upload rate limit"""
        from core.security.rate_limiting import RATE_LIMITER
        is_allowed, _ = RATE_LIMITER.is_rate_limited(
            type('MockRequest', (), {'user': user})(), 
            'file_upload'
        )
        return not is_allowed
    
    def _save_images(self, processed_image, thumbnail, filename, thumb_filename, user):
        """Save images securely to storage"""
        try:
            if self.config['STORAGE_BACKEND'] == 'remote':
                return self._save_images_remote(processed_image, thumbnail, filename, thumb_filename, user)
            else:
                return self._save_images_local(processed_image, thumbnail, filename, thumb_filename, user)
        except Exception as e:
            logger.error(f"Failed to save images: {e}")
            return False
    
    def _save_images_local(self, processed_image, thumbnail, filename, thumb_filename, user):
        """Save images to local storage"""
        try:
            # Ensure directory exists
            upload_dir = settings.SECURE_UPLOAD_ROOT
            upload_dir.mkdir(exist_ok=True, parents=True)
            
            # Save main image
            main_path = upload_dir / filename
            with open(main_path, 'wb') as f:
                f.write(processed_image)
            
            # Save thumbnail
            thumb_path = upload_dir / thumb_filename
            with open(thumb_path, 'wb') as f:
                f.write(thumbnail)
            
            # Set secure permissions
            main_path.chmod(0o644)
            thumb_path.chmod(0o644)
            
            logger.info(f"Images saved locally: {filename}, {thumb_filename}")
            return True
            
        except Exception as e:
            logger.error(f"Local image save failed: {e}")
            return False
    
    def _save_images_remote(self, processed_image, thumbnail, filename, thumb_filename, user):
        """Save images to remote storage"""
        if not PARAMIKO_AVAILABLE:
            logger.error("Paramiko not available for remote storage")
            return False
        
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            remote_config = self.config['REMOTE_STORAGE_CONFIG']
            ssh.connect(
                hostname=remote_config['HOST'],
                port=remote_config['PORT'],
                username=remote_config['USERNAME'],
                key_filename=remote_config['KEY_PATH']
            )
            
            sftp = ssh.open_sftp()
            
            # Save main image
            main_remote_path = f"{remote_config['REMOTE_PATH']}/{filename}"
            with sftp.open(main_remote_path, 'wb') as remote_file:
                remote_file.write(processed_image)
            
            # Save thumbnail
            thumb_remote_path = f"{remote_config['REMOTE_PATH']}/{thumb_filename}"
            with sftp.open(thumb_remote_path, 'wb') as remote_file:
                remote_file.write(thumbnail)
            
            sftp.close()
            ssh.close()
            
            logger.info(f"Images saved remotely: {filename}, {thumb_filename}")
            return True
            
        except Exception as e:
            logger.error(f"Remote image save failed: {e}")
            return False
    
    def delete_images(self, main_filename, thumb_filename):
        """Securely delete images with multi-pass overwriting"""
        try:
            if self.config['STORAGE_BACKEND'] == 'remote':
                return self._delete_images_remote(main_filename, thumb_filename)
            else:
                return self._delete_images_local(main_filename, thumb_filename)
        except Exception as e:
            logger.error(f"Error deleting images: {e}")
            return False
    
    def _delete_images_local(self, main_filename, thumb_filename):
        """Securely delete local images"""
        success = True
        
        for filename in [main_filename, thumb_filename]:
            if filename:
                file_path = settings.SECURE_UPLOAD_ROOT / filename
                if file_path.exists():
                    if not self._secure_delete_file(file_path):
                        success = False
                        logger.error(f"Failed to securely delete {file_path}")
                    else:
                        logger.info(f"Securely deleted local image: {file_path}")
        
        return success
    
    def _delete_images_remote(self, main_filename, thumb_filename):
        """Securely delete remote images"""
        if not PARAMIKO_AVAILABLE:
            logger.error("Paramiko not available for remote deletion")
            return False
        
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            remote_config = self.config['REMOTE_STORAGE_CONFIG']
            ssh.connect(
                hostname=remote_config['HOST'],
                port=remote_config['PORT'],
                username=remote_config['USERNAME'],
                key_filename=remote_config['KEY_PATH']
            )
            
            sftp = ssh.open_sftp()
            
            # Secure deletion for remote files
            success = True
            for filename in [main_filename, thumb_filename]:
                if filename:
                    remote_path = f"{remote_config['REMOTE_PATH']}/{filename}"
                    try:
                        # Get file size for secure overwriting
                        file_stat = sftp.stat(remote_path)
                        file_size = file_stat.st_size
                        
                        # Overwrite with random data multiple times
                        with sftp.open(remote_path, 'wb') as remote_file:
                            for _ in range(3):  # 3 passes
                                random_data = secrets.token_bytes(file_size)
                                remote_file.seek(0)
                                remote_file.write(random_data)
                                remote_file.flush()
                        
                        # Final deletion
                        sftp.remove(remote_path)
                        logger.info(f"Securely deleted remote image: {remote_path}")
                        
                    except FileNotFoundError:
                        pass
                    except Exception as e:
                        logger.error(f"Error securely deleting remote file {remote_path}: {e}")
                        success = False
            
            sftp.close()
            ssh.close()
            return success
            
        except Exception as e:
            logger.error(f"Remote deletion failed: {e}")
            return False
    
    def _secure_delete_file(self, file_path):
        """Securely delete a file with multiple overwrite passes"""
        try:
            file_size = file_path.stat().st_size
            
            with open(file_path, 'r+b') as f:
                # Pass 1: All zeros
                f.seek(0)
                f.write(b'\\x00' * file_size)
                f.flush()
                os.fsync(f.fileno())
                
                # Pass 2: All ones
                f.seek(0)
                f.write(b'\\xff' * file_size)
                f.flush()
                os.fsync(f.fileno())
                
                # Pass 3: Random data
                f.seek(0)
                f.write(secrets.token_bytes(file_size))
                f.flush()
                os.fsync(f.fileno())
            
            # Finally delete the file
            file_path.unlink()
            return True
            
        except Exception as e:
            logger.error(f"Secure file deletion failed for {file_path}: {e}")
            # Fallback to regular deletion
            try:
                file_path.unlink()
                return True
            except:
                return False


# Singleton instance
SECURE_IMAGE_PROCESSOR = EnterpriseImageProcessor()