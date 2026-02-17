#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test script to verify the login endpoint handles exceptions correctly.
This simulates the login flow without 500 errors.
"""
import os
import sys
import django
from django.test import RequestFactory, TestCase
from django.contrib.auth import get_user_model

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.config.settings.development')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from rest_framework.test import APIClient
from rest_framework import status

User = get_user_model()

def test_login_endpoint():
    """Test the login endpoint with a valid verified user."""
    print("=" * 80)
    print("Testing Login Endpoint Fix")
    print("=" * 80)
    
    # Create test user
    test_email = 'test@example.com'
    test_password = 'TestPassword123!'
    
    # Remove user if exists
    User.objects.filter(email=test_email).delete()
    
    # Create a new user
    user = User.objects.create_user(
        email=test_email,
        password=test_password,
        is_verified=True,
        is_active=True,
        first_name='Test',
        last_name='User'
    )
    print("[OK] Created test user: {}".format(test_email))
    print("  - is_verified: {}".format(user.is_verified))
    print("  - is_active: {}".format(user.is_active))
    
    # Test login
    client = APIClient()
    
    print("\nAttempting login...")
    response = client.post('/api/v1/auth/login/', {
        'email': test_email,
        'password': test_password,
        'device_fingerprint': 'test-fingerprint-123'
    }, format='json')
    
    print("Response Status Code: {}".format(response.status_code))
    print("Response Data: {}".format(response.data))
    
    # Check for 500 error
    if response.status_code == 500:
        print("\n[FAIL] ERROR: Login returned 500 - The fix did not work")
        return False
    
    # Check for successful login
    if response.status_code == 200:
        data = response.data
        if 'access' in data and 'refresh' in data:
            print("\n[OK] Login successful!")
            print("  - Access token received: {} chars".format(len(data['access'])))
            print("  - Refresh token received: {} chars".format(len(data['refresh'])))
            print("  - User data: {}".format(data.get('user', {})))
            return True
        elif 'requires_2fa' in data and data.get('requires_2fa'):
            print("\n[OK] Login requires 2FA (expected for suspicious activity detection)")
            return True
        else:
            print("\n[WARN] Unexpected response structure")
            return False
    
    # Check for auth errors (401)
    elif response.status_code == 401:
        print("\n[WARN] Authentication failed: {}".format(response.data))
        return False
    
    else:
        print("\n[WARN] Unexpected status code: {}".format(response.status_code))
        return False

def test_invalid_credentials():
    """Test login with invalid credentials."""
    print("\n" + "=" * 80)
    print("Testing Invalid Credentials Handling")
    print("=" * 80)
    
    client = APIClient()
    response = client.post('/api/v1/auth/login/', {
        'email': 'nonexistent@example.com',
        'password': 'wrongpassword',
        'device_fingerprint': 'test-fingerprint-123'
    }, format='json')
    
    print("Response Status Code: {}".format(response.status_code))
    
    if response.status_code == 500:
        print("[FAIL] ERROR: Invalid credentials returned 500 - Exception not handled")
        return False
    elif response.status_code == 401:
        print("[OK] Invalid credentials properly rejected with 401")
        return True
    else:
        print("[WARN] Unexpected status code: {}".format(response.status_code))
        return False

def test_unverified_user():
    """Test login with unverified user."""
    print("\n" + "=" * 80)
    print("Testing Unverified User Handling")
    print("=" * 80)
    
    # Create unverified user
    test_email = 'unverified@example.com'
    test_password = 'TestPassword123!'
    
    User.objects.filter(email=test_email).delete()
    user = User.objects.create_user(
        email=test_email,
        password=test_password,
        is_verified=False,
        is_active=True
    )
    print("[OK] Created unverified user: {}".format(test_email))
    
    client = APIClient()
    response = client.post('/api/v1/auth/login/', {
        'email': test_email,
        'password': test_password,
        'device_fingerprint': 'test-fingerprint-123'
    }, format='json')
    
    print("Response Status Code: {}".format(response.status_code))
    
    if response.status_code == 500:
        print("[FAIL] ERROR: Unverified user login returned 500")
        return False
    elif response.status_code == 401:
        print("[OK] Unverified user properly rejected with 401: {}".format(response.data))
        return True
    else:
        print("[WARN] Unexpected status code: {}".format(response.status_code))
        return False

if __name__ == '__main__':
    results = {
        'Valid Login': test_login_endpoint(),
        'Invalid Credentials': test_invalid_credentials(),
        'Unverified User': test_unverified_user(),
    }
    
    print("\n" + "=" * 80)
    print("Test Results Summary")
    print("=" * 80)
    for test_name, passed in results.items():
        status_text = "[PASS]" if passed else "[FAIL]"
        print("{}: {}".format(status_text, test_name))
    
    all_passed = all(results.values())
    print("\n" + ("=" * 80))
    if all_passed:
        print("[OK] All tests passed! The login endpoint is working correctly.")
    else:
        print("[WARN] Some tests failed. Please review the output above.")
    print("=" * 80)
    
    sys.exit(0 if all_passed else 1)
