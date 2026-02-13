"""
Encryption utilities for Software Distribution Platform.
"""
import hashlib
import hmac
import base64
import os
import time
import secrets
import string
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from django.conf import settings


class EncryptionManager:
    """
    Manager for encryption operations.
    Generates the Fernet key once during initialisation for performance.
    """

    def __init__(self):
        # Use Django's SECRET_KEY as base for encryption key
        self.secret_key = settings.SECRET_KEY.encode()
        self.salt = b'software_platform_salt'  # In production, store this securely
        self._key = None  # Lazy generation or generate immediately? Generate now.

    def _get_key(self):
        """Generate and cache the encryption key."""
        if self._key is None:
            self._key = self._derive_key()
        return self._key

    def _derive_key(self):
        """Derive a Fernet-compatible key from the secret key and salt."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.secret_key))
        return key

    def encrypt(self, data):
        """Encrypt data using the cached Fernet key."""
        if isinstance(data, str):
            data = data.encode()
        fernet = Fernet(self._get_key())
        return fernet.encrypt(data)

    def decrypt(self, encrypted_data):
        """Decrypt data using the cached Fernet key."""
        fernet = Fernet(self._get_key())
        decrypted = fernet.decrypt(encrypted_data)
        return decrypted.decode()

    def encrypt_activation_code(self, code):
        """Encrypt activation code with a timestamp to prevent replay attacks."""
        timestamp = str(int(time.time()))
        data = f"{code}|{timestamp}"
        return self.encrypt(data)

    def decrypt_activation_code(self, encrypted_code):
        """
        Decrypt activation code and validate that it is not older than 5 minutes.
        Returns the code if valid, otherwise None.
        """
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
        """Generate hash for activation code using the Django SECRET_KEY as salt."""
        salt = settings.SECRET_KEY.encode()
        return HashManager.hmac_sha256(salt, code)


class KeyGenerator:
    """Generate secure keys and codes."""

    @staticmethod
    def generate_activation_code(length=25):
        """
        Generate an activation code.
        Uses ACTIVATION_KEY_CHARS from settings, or falls back to alphanumeric.
        """
        # Get allowed characters from settings or use a safe default
        chars = getattr(settings, 'ACTIVATION_KEY_CHARS',
                        'ABCDEFGHJKLMNPQRSTUVWXYZ23456789')
        # Generate in groups of 4 with dashes
        code_parts = []
        for _ in range(length // 4):
            part = ''.join(secrets.choice(chars) for _ in range(4))
            code_parts.append(part)
        code = '-'.join(code_parts)
        # Ensure we have the right total length (excluding dashes)
        raw_length = len(code.replace('-', ''))
        if raw_length < length:
            extra = ''.join(secrets.choice(chars) for _ in range(length - raw_length))
            code += extra
        return code[:length]  # Slice to exact length

    @staticmethod
    def generate_api_key():
        """Generate a 32‑character API key (letters + digits)."""
        chars = string.ascii_letters + string.digits
        return ''.join(secrets.choice(chars) for _ in range(32))

    @staticmethod
    def generate_secure_token(length=64):
        """Generate a cryptographically secure URL‑safe token."""
        return secrets.token_urlsafe(length)