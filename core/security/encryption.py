import os
import secrets
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class FieldEncryption:
    def __init__(self):
        self._key = self._get_encryption_key()
        self._fernet = Fernet(self._key)
    
    def _get_encryption_key(self):
        """Get or generate encryption key"""
        key_material = os.environ.get('MASTER_PASSWORD', '').encode()
        salt = os.environ.get('MASTER_SALT', secrets.token_bytes(32))
        
        if isinstance(salt, str):
            salt = base64.b64decode(salt)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,
        )
        
        key = base64.urlsafe_b64encode(kdf.derive(key_material))
        return key
    
    def encrypt(self, data):
        """Encrypt sensitive field data"""
        if not data:
            return data
        
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        encrypted = self._fernet.encrypt(data)
        return base64.urlsafe_b64encode(encrypted).decode('utf-8')
    
    def decrypt(self, encrypted_data):
        """Decrypt sensitive field data"""
        if not encrypted_data:
            return encrypted_data
        
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode('utf-8'))
            decrypted = self._fernet.decrypt(encrypted_bytes)
            return decrypted.decode('utf-8')
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            return None


class AsymmetricEncryption:
    def __init__(self):
        self.key_size = 4096
    
    def generate_key_pair(self):
        """Generate RSA key pair for asymmetric encryption"""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=self.key_size,
        )
        
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        public_key = private_key.public_key()
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        return {
            'private_key': private_pem.decode('utf-8'),
            'public_key': public_pem.decode('utf-8')
        }
    
    def encrypt_with_public_key(self, message, public_key_pem):
        """Encrypt message with public key"""
        try:
            public_key = serialization.load_pem_public_key(public_key_pem.encode())
            
            if isinstance(message, str):
                message = message.encode('utf-8')
            
            encrypted = public_key.encrypt(
                message,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            return base64.urlsafe_b64encode(encrypted).decode('utf-8')
        
        except Exception as e:
            logger.error(f"Public key encryption failed: {e}")
            return None
    
    def decrypt_with_private_key(self, encrypted_message, private_key_pem):
        """Decrypt message with private key"""
        try:
            private_key = serialization.load_pem_private_key(
                private_key_pem.encode(),
                password=None,
            )
            
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_message.encode())
            
            decrypted = private_key.decrypt(
                encrypted_bytes,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            return decrypted.decode('utf-8')
        
        except Exception as e:
            logger.error(f"Private key decryption failed: {e}")
            return None


class StreamEncryption:
    def __init__(self):
        self.algorithm = algorithms.AES256
        self.mode_class = modes.GCM
    
    def encrypt_stream(self, data, key=None):
        """Encrypt large data streams"""
        if key is None:
            key = secrets.token_bytes(32)
        
        iv = secrets.token_bytes(12)  # 96-bit IV for GCM
        cipher = Cipher(self.algorithm(key), self.mode_class(iv))
        encryptor = cipher.encryptor()
        
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        ciphertext = encryptor.update(data) + encryptor.finalize()
        
        return {
            'key': base64.urlsafe_b64encode(key).decode('utf-8'),
            'iv': base64.urlsafe_b64encode(iv).decode('utf-8'),
            'ciphertext': base64.urlsafe_b64encode(ciphertext).decode('utf-8'),
            'tag': base64.urlsafe_b64encode(encryptor.tag).decode('utf-8')
        }
    
    def decrypt_stream(self, encrypted_data):
        """Decrypt large data streams"""
        try:
            key = base64.urlsafe_b64decode(encrypted_data['key'])
            iv = base64.urlsafe_b64decode(encrypted_data['iv'])
            ciphertext = base64.urlsafe_b64decode(encrypted_data['ciphertext'])
            tag = base64.urlsafe_b64decode(encrypted_data['tag'])
            
            cipher = Cipher(self.algorithm(key), self.mode_class(iv, tag))
            decryptor = cipher.decryptor()
            
            plaintext = decryptor.update(ciphertext) + decryptor.finalize()
            return plaintext.decode('utf-8')
        
        except Exception as e:
            logger.error(f"Stream decryption failed: {e}")
            return None


FIELD_ENCRYPTION = FieldEncryption()
ASYMMETRIC_ENCRYPTION = AsymmetricEncryption()
STREAM_ENCRYPTION = StreamEncryption()