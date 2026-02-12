# FILE: /backend/apps/licenses/utils/encryption.py
import base64
import json
import os
import logging
import hashlib
from cryptography.fernet import Fernet
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class LicenseEncryptionManager:
    """
    License Encryption Manager.
    
    - Symmetric encryption via Fernet (AES-128-CBC).
    - Supports both legacy (v1.0) and enhanced (v1.1) license files.
    - Enhanced version adds expiry, hardware binding, and integrity signature.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        self.symmetric_key = self._load_or_generate_symmetric_key()

    def _load_or_generate_symmetric_key(self):
        """
        Load symmetric key from file, generate + save if path is given,
        or derive a deterministic key from SECRET_KEY as fallback.
        """
        key_config = settings.LICENSE_KEY_SETTINGS
        key_path = key_config.get('LICENSE_ENCRYPTION_KEY_PATH')

        if key_path and os.path.exists(key_path):
            # 1. Load existing key from file
            with open(key_path, 'rb') as f:
                key = f.read()
            logger.info(f"Loaded encryption key from {key_path}")
            return Fernet(key)

        if key_path:
            # 2. Path provided but file missing → generate new key and save it
            key = Fernet.generate_key()
            os.makedirs(os.path.dirname(key_path), exist_ok=True)
            with open(key_path, 'wb') as f:
                f.write(key)
            logger.info(f"Generated and saved new encryption key to {key_path}")
            return Fernet(key)

        # 3. No path configured → deterministic fallback from SECRET_KEY
        #    This ensures the key remains stable across container restarts.
        key = base64.urlsafe_b64encode(
            hashlib.sha256(settings.SECRET_KEY.encode()).digest()
        )
        logger.warning("No LICENSE_ENCRYPTION_KEY_PATH set. "
                       "Using deterministic key derived from SECRET_KEY.")
        return Fernet(key)

    def encrypt_license_data(self, data):
        """Encrypt license data (returns dict with base64 encrypted payload)."""
        json_data = json.dumps(data, separators=(',', ':')).encode()
        encrypted = self.symmetric_key.encrypt(json_data)
        return {
            'encrypted_data': base64.urlsafe_b64encode(encrypted).decode(),
            'algorithm': 'FERNET-AES128-CBC',  # Updated label
            'timestamp': self._get_timestamp()
        }

    def decrypt_license_data(self, encrypted_package):
        """Decrypt and return license data, or None on failure."""
        try:
            encrypted = base64.urlsafe_b64decode(
                encrypted_package['encrypted_data'].encode()
            )
            decrypted = self.symmetric_key.decrypt(encrypted)
            return json.loads(decrypted.decode())
        except Exception as e:
            logger.error(f"License decryption failed: {str(e)}")
            return None

    # ------------------------------------------------------------------
    # LEGACY METHOD – kept for backward compatibility (v1.0)
    # ------------------------------------------------------------------
    def create_license_file(self, license_data, filename=None):
        """
        Legacy license file creation (v1.0).
        - No expiry, no hardware binding, no signature.
        - Accepts optional filename to write to disk.
        Returns bytes of the JSON license file.
        """
        encrypted_package = self.encrypt_license_data(license_data)
        license_file = {
            'header': {
                'version': '1.0',
                'generator': 'Software Distribution Platform',
                'format': 'JSON_ENCRYPTED'
            },
            'license': encrypted_package
        }
        license_json = json.dumps(license_file, indent=2)
        if filename:
            with open(filename, 'w') as f:
                f.write(license_json)
        return license_json.encode()

    # ------------------------------------------------------------------
    # ENHANCED METHOD – v1.1 with expiry, hardware binding, signature
    # ------------------------------------------------------------------
    def create_license_file_with_binding(
        self,
        license_data,
        hardware_id=None,
        expiry_days=365
    ):
        """
        Create an enhanced license file (v1.1) with:
        - Expiry date (expiry_days from now)
        - Optional hardware binding (hardware_id)
        - Integrity signature (SHA256 of encrypted payload)
        Returns bytes of the JSON license file.
        """
        now = timezone.now()
        expiry_date = now + timezone.timedelta(days=expiry_days)

        # Payload includes metadata + original claims
        payload = {
            'claims': license_data,
            'expires_at': int(expiry_date.timestamp()),
            'issued_at': self._get_timestamp(),
            'hardware_id': hardware_id
        }

        encrypted_package = self.encrypt_license_data(payload)

        license_file = {
            'header': {
                'version': '1.1',
                'generator': 'Software Distribution Platform',
                'format': 'JSON_ENCRYPTED_V2'
            },
            'license': encrypted_package,
            'signature': hashlib.sha256(
                encrypted_package['encrypted_data'].encode()
            ).hexdigest()
        }

        return json.dumps(license_file, indent=2).encode()

    # ------------------------------------------------------------------
    # UNIVERSAL VALIDATOR – works with v1.0 and v1.1
    # ------------------------------------------------------------------
    def validate_license_file(self, license_content, current_hardware_id=None):
        """
        Validate a license file (both legacy v1.0 and enhanced v1.1).
        
        - Decrypts the license data.
        - For v1.1 files:
            * Verifies signature integrity.
            * Checks expiry (if present).
            * Validates hardware binding (if present and `current_hardware_id` provided).
        - For v1.0 files, only decryption is required.
        
        Returns:
            dict: {'valid': bool, 'data': dict, 'error': str, ...}
        """
        try:
            # Parse JSON
            if isinstance(license_content, bytes):
                license_content = license_content.decode()
            license_full = json.loads(license_content)

            header = license_full.get('header', {})
            version = header.get('version', '1.0')
            generator = header.get('generator')

            # Verify generator (both versions)
            if generator != 'Software Distribution Platform':
                return {'valid': False, 'error': 'Invalid license generator'}

            # --- Integrity check (v1.1 only) ---
            if version == '1.1':
                expected_sig = hashlib.sha256(
                    license_full['license']['encrypted_data'].encode()
                ).hexdigest()
                if license_full.get('signature') != expected_sig:
                    return {'valid': False, 'error': 'License tampered or corrupt'}

            # --- Decryption ---
            payload = self.decrypt_license_data(license_full['license'])
            if not payload:
                return {'valid': False, 'error': 'License decryption failed'}

            # --- Handle v1.1 metadata ---
            if version == '1.1':
                # Expiry check
                if timezone.now().timestamp() > payload.get('expires_at', 0):
                    return {'valid': False, 'error': 'License has expired'}

                # Hardware binding check (if current_hardware_id provided)
                if current_hardware_id and payload.get('hardware_id'):
                    if payload['hardware_id'] != current_hardware_id:
                        return {
                            'valid': False,
                            'error': 'License bound to different hardware'
                        }

                # Extract the actual claims
                license_data = payload['claims']
            else:
                # v1.0: payload is directly the license data
                license_data = payload

            return {
                'valid': True,
                'data': license_data,
                'header': header,
                'version': version
            }

        except Exception as e:
            logger.error(f"License validation critical failure: {e}")
            return {'valid': False, 'error': 'Malformed license file'}

    def _get_timestamp(self):
        """Return current Unix timestamp."""
        return int(timezone.now().timestamp())