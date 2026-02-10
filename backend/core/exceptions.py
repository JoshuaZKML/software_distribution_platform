"""
Custom exceptions for Software Distribution Platform.
"""
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

def custom_exception_handler(exc, context):
    """Custom exception handler for DRF."""
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)
    
    if response is not None:
        # Customize the response data
        response.data = {
            'error': True,
            'code': response.status_code,
            'message': response.data.get('detail', str(exc)),
            'details': response.data
        }
    else:
        # Handle uncaught exceptions
        response = Response({
            'error': True,
            'code': status.HTTP_500_INTERNAL_SERVER_ERROR,
            'message': 'Internal server error',
            'details': str(exc)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return response


class LicenseValidationError(Exception):
    """Exception raised for license validation errors."""
    pass


class ActivationError(Exception):
    """Exception raised for activation errors."""
    pass


class PaymentError(Exception):
    """Exception raised for payment errors."""
    pass


class SecurityViolationError(Exception):
    """Exception raised for security violations."""
    pass
