"""
Custom exceptions and DRF exception handler for Software Distribution Platform.
"""
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import APIException


def custom_exception_handler(exc, context):
    """
    Custom exception handler for DRF.
    Standardizes all API error responses into a consistent format.
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)

    if response is not None:
        # Standardize the error payload
        # response.data may be a dict, list, or string; we preserve it in 'details'
        error_detail = response.data.get('detail', 'A server error occurred.')
        if isinstance(response.data, dict) and 'detail' in response.data:
            # DRF typically puts the main message under 'detail'
            message = response.data['detail']
        else:
            # For non-dict responses (e.g., plain string) or when 'detail' is missing
            message = error_detail

        custom_data = {
            'error': True,
            'code': response.status_code,
            'message': message,
            'details': response.data   # Preserve full original DRF error structure
        }
        response.data = custom_data
    else:
        # Catch any exception not handled by DRF (including our legacy custom exceptions)
        # Ensure we don't crash on __str__ if it's not implemented
        try:
            exc_str = str(exc)
        except Exception:
            exc_str = None

        response = Response({
            'error': True,
            'code': status.HTTP_500_INTERNAL_SERVER_ERROR,
            'message': 'Internal server error',
            'details': exc_str
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return response


class LicenseValidationError(APIException):
    """
    Exception raised for license validation errors.
    Automatically returns HTTP 402 Payment Required.
    """
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    default_detail = 'The provided license key is invalid or expired.'
    default_code = 'license_invalid'


class ActivationError(APIException):
    """
    Exception raised for activation errors (e.g., device limit reached).
    Automatically returns HTTP 400 Bad Request.
    """
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Device activation limit reached.'
    default_code = 'activation_failed'


class PaymentError(APIException):
    """
    Exception raised for payment processing errors.
    Automatically returns HTTP 402 Payment Required.
    """
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    default_detail = 'Transaction could not be completed.'
    default_code = 'payment_failed'


class SecurityViolationError(APIException):
    """
    Exception raised for security violations.
    Automatically returns HTTP 403 Forbidden.
    """
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'Security integrity check failed.'
    default_code = 'security_violation'
