# FILE: /backend/apps/licenses/management/commands/setup_encryption.py
from django.core.management.base import BaseCommand
import os
import secrets
from pathlib import Path
from django.conf import settings


class Command(BaseCommand):
    help = "Setup encryption keys for license system"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force regeneration of keys even if they already exist",
        )
        parser.add_argument(
            "--output-dir",
            type=str,
            help="Directory to save keys (default: <BASE_DIR>/license_keys)",
        )

    def handle(self, *args, **options):
        from cryptography.fernet import Fernet
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization

        output_dir = Path(options["output_dir"] or settings.BASE_DIR) / "license_keys"
        output_dir.mkdir(parents=True, exist_ok=True)

        self.stdout.write(f"Target directory: {output_dir}")

        # ------------------------------------------------------------------
        # 1. Symmetric key (Fernet) – used by LicenseEncryptionManager
        # ------------------------------------------------------------------
        sym_path = output_dir / "symmetric.key"
        if not sym_path.exists() or options["force"]:
            sym_path.write_bytes(Fernet.generate_key())
            self.stdout.write(self.style.SUCCESS("✓ Symmetric key generated"))

        # ------------------------------------------------------------------
        # 2. RSA key pair (optional – reserved for future asymmetric use)
        #    Not currently used, but safe to generate.
        # ------------------------------------------------------------------
        priv_path = output_dir / "private.pem"
        pub_path = output_dir / "public.pem"
        if not priv_path.exists() or options["force"]:
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
            )

            # Save private key (no encryption – file permissions will protect it)
            priv_path.write_bytes(
                private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )
            # Save public key
            pub_path.write_bytes(
                private_key.public_key().public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo,
                )
            )
            self.stdout.write(self.style.SUCCESS("✓ RSA key pair generated"))

        # ------------------------------------------------------------------
        # 3. Persistent hardware ID salt – used by LICENSE_KEY_SETTINGS
        # ------------------------------------------------------------------
        snippet_path = output_dir / "env_snippet.txt"
        salt = secrets.token_hex(32)

        if snippet_path.exists() and not options["force"]:
            self.stdout.write(
                "Existing env_snippet.txt found. Keeping existing SALT "
                "to avoid hardware‑ID mismatch. (Use --force to regenerate.)"
            )
        else:
            env_content = f"""
# --- LICENSE SYSTEM CONFIG ---
LICENSE_ENCRYPTION_KEY_PATH={sym_path}
LICENSE_PRIVATE_KEY_PATH={priv_path}
LICENSE_PUBLIC_KEY_PATH={pub_path}
HARDWARE_ID_SALT={salt}
"""
            snippet_path.write_text(env_content.strip())
            self.stdout.write(
                self.style.SUCCESS(f"✓ Environment snippet written to {snippet_path}")
            )

        # ------------------------------------------------------------------
        # 4. Secure file permissions (Unix only)
        # ------------------------------------------------------------------
        if os.name != "nt":
            os.chmod(sym_path, 0o600)
            os.chmod(priv_path, 0o600)
            self.stdout.write("✓ Set secure permissions (600) on private key files")

        self.stdout.write(
            self.style.HTTP_INFO(
                "\nAction Required: Copy the contents of env_snippet.txt to your .env file."
            )
        )