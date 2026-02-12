# FILE: /backend/apps/accounts/tests/test_tasks.py
from django.test import TestCase
from django.core import mail
from unittest.mock import patch, MagicMock
from backend.apps.accounts.models import User
from backend.apps.accounts.tasks import (
    send_verification_email,
    send_password_reset_email,
    send_welcome_email,
    send_device_verification_email
)

class TasksTestCase(TestCase):
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
    
    @patch('backend.apps.accounts.tasks.render_to_string')
    @patch('backend.apps.accounts.tasks.EmailMultiAlternatives')
    def test_send_verification_email(self, mock_email, mock_render):
        """Test verification email task."""
        # Mock the email response
        mock_email_instance = MagicMock()
        mock_email.return_value = mock_email_instance
        mock_render.side_effect = ['html_content', 'text_content']
        
        # Call the task
        result = send_verification_email(str(self.user.id))
        
        # Verify email was sent
        mock_email.assert_called_once()
        mock_email_instance.send.assert_called_once_with(fail_silently=False)
        
        self.assertEqual(result['status'], 'success')
        self.assertIn('test@example.com', result['message'])
    
    @patch('backend.apps.accounts.tasks.render_to_string')
    @patch('backend.apps.accounts.tasks.EmailMultiAlternatives')
    def test_send_password_reset_email(self, mock_email, mock_render):
        """Test password reset email task."""
        # Mock the email response
        mock_email_instance = MagicMock()
        mock_email.return_value = mock_email_instance
        mock_render.side_effect = ['html_content', 'text_content']
        
        # Call the task with a test token
        test_token = 'test_token_123'
        result = send_password_reset_email(str(self.user.id), test_token)
        
        # Verify email was sent
        mock_email.assert_called_once()
        mock_email_instance.send.assert_called_once_with(fail_silently=False)
        
        self.assertEqual(result['status'], 'success')
        self.assertIn('test@example.com', result['message'])
    
    def test_send_welcome_email_skips_unverified(self):
        """Test welcome email skips unverified users."""
        self.user.is_verified = False
        self.user.save()
        
        result = send_welcome_email(str(self.user.id))
        
        self.assertEqual(result['status'], 'skipped')
        self.assertEqual(result['message'], 'User not verified')
    
    @patch('backend.apps.accounts.utils.device_verification.DeviceVerificationManager')
    @patch('backend.apps.accounts.tasks.render_to_string')
    @patch('backend.apps.accounts.tasks.EmailMultiAlternatives')
    def test_send_device_verification_email(self, mock_email, mock_render, mock_device_manager):
        """Test device verification email task."""
        # Mock device verification manager
        mock_device_manager.create_verification_token.return_value = {
            'token': 'test_token',
            'expires_at': '2024-01-01T00:00:00Z'
        }
        mock_device_manager._generate_expected_code.return_value = 'ABC123'
        
        # Mock email
        mock_email_instance = MagicMock()
        mock_email.return_value = mock_email_instance
        mock_render.side_effect = ['html_content', 'text_content']
        
        # Call the task
        result = send_device_verification_email(
            str(self.user.id),
            'device_fingerprint_123',
            '192.168.1.1',
            'Test Browser'
        )
        
        # Verify email was sent
        mock_email.assert_called_once()
        mock_email_instance.send.assert_called_once_with(fail_silently=False)
        
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['token'], 'test_token')
    
    def tearDown(self):
        self.user.delete()