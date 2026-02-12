# FILE: /backend/apps/licenses/utils/key_generation.py
import secrets
import hashlib
import hmac
from django.conf import settings
from django.utils import timezone


class ActivationKeyGenerator:
    """
    Generate cryptographically secure activation keys with software binding.
    Uses HMAC‑SHA256 for proof – no encryption overhead.
    """

    CHAR_SET_STANDARD = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    CHAR_SET_EXTENDED = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789!@#$%^&*"
    CHAR_SET_ALPHANUM = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

    @staticmethod
    def generate_secure_key(key_format="STANDARD", length=25, groups=4):
        """Generate a random activation key in the specified format."""
        chars = getattr(ActivationKeyGenerator, f"CHAR_SET_{key_format}",
                        ActivationKeyGenerator.CHAR_SET_STANDARD)
        chars_per_group = length // groups
        remainder = length % groups

        key_parts = []
        for i in range(groups):
            part_len = chars_per_group + (1 if i < remainder else 0)
            part = ''.join(secrets.choice(chars) for _ in range(part_len))
            key_parts.append(part)

        return '-'.join(key_parts)[:length]

    @staticmethod
    def generate_software_bound_key(software_id, user_id=None, key_format="STANDARD", length=25):
        """
        Generate an activation key cryptographically bound to a specific software.
        Returns dict with key, hash, proof, and metadata.
        """
        random_seed = secrets.token_bytes(32)
        derivation_data = f"{software_id}"
        if user_id:
            derivation_data += f"|{user_id}"
        derivation_data += f"|{int(timezone.now().timestamp())}|{random_seed.hex()}"

        key_hash = hashlib.sha256(derivation_data.encode()).hexdigest()
        chars = getattr(ActivationKeyGenerator, f"CHAR_SET_{key_format}",
                        ActivationKeyGenerator.CHAR_SET_STANDARD)
        key_bytes = bytes.fromhex(key_hash)
        key_chars = []
        for byte in key_bytes[:length]:
            key_chars.append(chars[byte % len(chars)])
        key = ''.join(key_chars)
        formatted_key = ActivationKeyGenerator._format_key(key, length)

        # HMAC proof – verifiable without storing the key in plaintext
        proof = hmac.new(
            key=settings.SECRET_KEY.encode(),
            msg=f"{software_id}|{formatted_key}".encode(),
            digestmod=hashlib.sha256
        ).hexdigest()

        return {
            'key': formatted_key,
            'key_hash': hashlib.sha256(formatted_key.encode()).hexdigest(),
            'proof': proof,
            'derivation_data': derivation_data,
            'software_id': str(software_id),
            'user_id': str(user_id) if user_id else None,
            'generated_at': timezone.now().isoformat()
        }

    @staticmethod
    def _format_key(key, length, groups=4):
        """Internal helper: format key into groups separated by dashes."""
        chars_per_group = length // groups
        remainder = length % groups
        parts = []
        start = 0
        for i in range(groups):
            part_len = chars_per_group + (1 if i < remainder else 0)
            parts.append(key[start:start + part_len])
            start += part_len
        return '-'.join(parts)

    @staticmethod
    def verify_software_binding(key, software_id, proof):
        """
        Verify that a key is bound to the given software ID.
        Returns bool.
        """
        expected = hmac.new(
            key=settings.SECRET_KEY.encode(),
            msg=f"{software_id}|{key}".encode(),
            digestmod=hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(proof, expected)

    @staticmethod
    def generate_batch_keys(software_id, count, key_format="STANDARD", length=25):
        """Generate multiple keys for the same software in one batch."""
        keys = []
        for _ in range(count):
            key_data = ActivationKeyGenerator.generate_software_bound_key(
                software_id=software_id,
                key_format=key_format,
                length=length
            )
            keys.append(key_data)
        return keys

    @staticmethod
    def validate_key_format(key, expected_format="STANDARD", expected_length=25):
        """
        Validate that a key matches the expected format and length.
        Returns dict with 'valid' bool and optional 'error'.
        """
        clean_key = key.replace('-', '')
        if len(clean_key) != expected_length:
            return {
                'valid': False,
                'error': f'Key length mismatch. Expected {expected_length}, got {len(clean_key)}'
            }
        chars = getattr(ActivationKeyGenerator, f"CHAR_SET_{expected_format}",
                        ActivationKeyGenerator.CHAR_SET_STANDARD)
        invalid_chars = set(clean_key) - set(chars)
        if invalid_chars:
            return {
                'valid': False,
                'error': f'Invalid characters: {", ".join(invalid_chars)}'
            }
        if '-' in key:
            parts = key.split('-')
            if len(parts) not in [4, 5]:
                return {
                    'valid': False,
                    'error': 'Invalid group format'
                }
        return {'valid': True}