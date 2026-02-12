# FILE: /backend/apps/licenses/tests/test_key_generation.py
from django.test import TestCase
from django.utils import timezone
from backend.apps.products.models import Software, Category
from backend.apps.accounts.models import User
from ..utils.key_generation import ActivationKeyGenerator
from ..utils.encryption import LicenseEncryptionManager


class KeyGenerationTests(TestCase):

    def setUp(self):
        category = Category.objects.create(
            name="Test Category",
            slug="test-category"
        )
        self.software = Software.objects.create(
            name="Test Software",
            slug="test-software",
            app_code="TEST001",
            category=category
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="Test@1234"
        )

    def test_secure_key_generation(self):
        key = ActivationKeyGenerator.generate_secure_key(
            key_format="STANDARD",
            length=25,
            groups=4
        )
        validation = ActivationKeyGenerator.validate_key_format(
            key=key,
            expected_format="STANDARD",
            expected_length=25
        )
        self.assertTrue(validation['valid'])
        self.assertEqual(len(key.replace('-', '')), 25)
        self.assertEqual(len(key.split('-')), 4)
        print("✅ Secure key generation test passed")

    def test_software_bound_key(self):
        key_data = ActivationKeyGenerator.generate_software_bound_key(
            software_id=self.software.id,
            user_id=self.user.id,
            key_format="STANDARD",
            length=25
        )
        self.assertIn('key', key_data)
        self.assertIn('key_hash', key_data)
        self.assertIn('proof', key_data)
        self.assertIn('software_id', key_data)
        self.assertIn('user_id', key_data)

        is_bound = ActivationKeyGenerator.verify_software_binding(
            key=key_data['key'],
            software_id=self.software.id,
            proof=key_data['proof']
        )
        self.assertTrue(is_bound)

        wrong_software_id = "00000000-0000-0000-0000-000000000000"
        is_bound_wrong = ActivationKeyGenerator.verify_software_binding(
            key=key_data['key'],
            software_id=wrong_software_id,
            proof=key_data['proof']
        )
        self.assertFalse(is_bound_wrong)
        print("✅ Software-bound key generation test passed")

    def test_key_batch_generation(self):
        batch_keys = ActivationKeyGenerator.generate_batch_keys(
            software_id=self.software.id,
            count=5,
            key_format="STANDARD",
            length=25
        )
        self.assertEqual(len(batch_keys), 5)
        keys = [k['key'] for k in batch_keys]
        self.assertEqual(len(set(keys)), 5)
        for key_data in batch_keys:
            is_bound = ActivationKeyGenerator.verify_software_binding(
                key=key_data['key'],
                software_id=self.software.id,
                proof=key_data['proof']
            )
            self.assertTrue(is_bound)
        print("✅ Batch key generation test passed")

    def test_license_encryption(self):
        encryption_manager = LicenseEncryptionManager()
        license_data = {
            'activation_code': 'ABCD-EFGH-IJKL-MNOP',
            'software': 'Test Software',
            'expires_at': '2026-12-31T23:59:59Z',
            'features': ['feature1', 'feature2']
        }
        encrypted_package = encryption_manager.encrypt_license_data(license_data)
        self.assertIn('encrypted_data', encrypted_package)
        self.assertIn('algorithm', encrypted_package)
        decrypted_data = encryption_manager.decrypt_license_data(encrypted_package)
        self.assertIsNotNone(decrypted_data)
        self.assertEqual(decrypted_data['activation_code'], license_data['activation_code'])
        print("✅ License encryption test passed")

    def test_license_file_creation(self):
        encryption_manager = LicenseEncryptionManager()
        license_data = {
            'activation_code': 'WXYZ-1234-5678-90AB',
            'software': {'name': 'Test Software', 'version': '1.0.0'},
            'validity': {'expires_at': '2026-12-31T23:59:59Z', 'max_activations': 3}
        }
        license_content = encryption_manager.create_license_file(license_data)
        validation_result = encryption_manager.validate_license_file(license_content)
        self.assertTrue(validation_result['valid'])
        self.assertEqual(validation_result['data']['activation_code'], license_data['activation_code'])
        print("✅ License file creation test passed")