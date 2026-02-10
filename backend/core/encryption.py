"""
Encryption utilities for Software Distribution Platform.
"""
import hashlib
import hmac
import base64
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from django.conf import settings

class EncryptionManager:
    """Manager for encryption operations."""
    
    def __init__(self):
        # Use Django's SECRET_KEY as base for encryption key
        self.secret_key = settings.SECRET_KEY.encode()
        self.salt = b'software_platform_salt'  # In production, store this securely
        
    def generate_key(self):
        """Generate encryption key from secret key."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.secret_key))
        return key
    
    def encrypt(self, data):
        """Encrypt data."""
        if isinstance(data, str):
            data = data.encode()
        
        key = self.generate_key()
        fernet = Fernet(key)
        encrypted = fernet.encrypt(data)
        return encrypted
    
    def decrypt(self, encrypted_data):
        """Decrypt data."""
        key = self.generate_key()
        fernet = Fernet(key)
        decrypted = fernet.decrypt(encrypted_data)
        return decrypted.decode()
    
    def encrypt_activation_code(self, code):
        """Encrypt activation code with additional security."""
        # Add timestamp to prevent replay attacks
        import time
        timestamp = str(int(time.time()))
        data = f"{code}|{timestamp}"
        return self.encrypt(data)
    
    def decrypt_activation_code(self, encrypted_code):
        """Decrypt activation code and validate timestamp."""
        try:
            decrypted = self.decrypt(encrypted_code)
            code, timestamp = decrypted.split('|')
            
            # Check if code is expired (more than 5 minutes old)
            current_time = int(time.time())
            if current_time - int(timestamp) > 300:  # 5 minutes
                return None
            
            return code
        except Exception:
            return None


class HashManager:
    """Manager for hashing operations."""
    
    @staticmethod
    def sha256(data):
        """Generate SHA-256 hash."""
        if isinstance(data, str):
            data = data.encode()
        return hashlib.sha256(data).hexdigest()
    
    @staticmethod
    def hmac_sha256(key, data):
        """Generate HMAC-SHA256 hash."""
        if isinstance(key, str):
            key = key.encode()
        if isinstance(data, str):
            data = data.encode()
        return hmac.new(key, data, hashlib.sha256).hexdigest()
    
    @staticmethod
    def generate_activation_code_hash(code):
        """Generate hash for activation code."""
        # Use a secret salt for activation codes
        salt = settings.SECRET_KEY.encode()
        return HashManager.hmac_sha256(salt, code)


class KeyGenerator:
    """Generate secure keys and codes."""
    
    @staticmethod
    def generate_activation_code(length=25):
        """Generate activation code."""
        import secrets
        import string
        
        # Characters to use (excluding confusing characters)
        chars = settings.ACTIVATION_KEY_CHARS
        
        # Generate code in groups of 4 with dashes
        code_parts = []
        for _ in range(length // 4):
            part = ''.join(secrets.choice(chars) for _ in range(4))
            code_parts.append(part)
        
        code = '-'.join(code_parts)
        
        # Ensure we have the right length
        if len(code) < length:
            extra = ''.join(secrets.choice(chars) for _ in range(length - len(code)))
            code += extra
        
        return code[:length]
    
    @staticmethod
    def generate_api_key():
        """Generate API key."""
        import secrets
        import string
        
        # Generate 32 character API key
        chars = string.ascii_letters + string.digits
        return ''.join(secrets.choice(chars) for _ in range(32))
    
    @staticmethod
    def generate_secure_token(length=64):
        """Generate secure token."""
        import secrets
        return secrets.token_urlsafe(length)
