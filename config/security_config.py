import os
import secrets
import hashlib
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import base64


class SecretManager:
    def __init__(self):
        self._master_key = self._derive_master_key()
        self._fernet = Fernet(self._master_key)
    
    def _derive_master_key(self):
        password = os.environ.get('MASTER_PASSWORD', '').encode()
        salt = os.environ.get('MASTER_SALT', secrets.token_bytes(32))
        if isinstance(salt, str):
            salt = base64.b64decode(salt)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))
        return key
    
    def encrypt_sensitive_data(self, data):
        if isinstance(data, str):
            data = data.encode()
        return self._fernet.encrypt(data)
    
    def decrypt_sensitive_data(self, encrypted_data):
        decrypted = self._fernet.decrypt(encrypted_data)
        return decrypted.decode()
    
    def generate_secure_token(self, length=64):
        return secrets.token_urlsafe(length)
    
    def generate_secure_key(self, length=32):
        return secrets.token_bytes(length)
    
    def secure_compare(self, val1, val2):
        return secrets.compare_digest(val1, val2)
    
    def hash_password(self, password, salt=None):
        if salt is None:
            salt = secrets.token_bytes(32)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=320000,
        )
        
        if isinstance(password, str):
            password = password.encode()
        
        key = kdf.derive(password)
        return base64.b64encode(salt + key).decode()
    
    def verify_password(self, password, hashed_password):
        try:
            decoded = base64.b64decode(hashed_password.encode())
            salt = decoded[:32]
            stored_key = decoded[32:]
            
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=320000,
            )
            
            if isinstance(password, str):
                password = password.encode()
            
            key = kdf.derive(password)
            return secrets.compare_digest(key, stored_key)
        except Exception:
            return False


class MemoryProtection:
    @staticmethod
    def secure_zero(data):
        if isinstance(data, str):
            data = data.encode()
        
        for i in range(len(data)):
            data[i:i+1] = b'\x00'
    
    @staticmethod
    def secure_random_fill(data):
        if isinstance(data, str):
            data = data.encode()
        
        for i in range(len(data)):
            data[i:i+1] = secrets.token_bytes(1)


SECRET_MANAGER = SecretManager()
MEMORY_PROTECTION = MemoryProtection()