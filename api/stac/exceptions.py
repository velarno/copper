"""
Custom exceptions for the STAC module.
"""

from typing import Optional, Dict, Any


class STACError(Exception):
    """Base exception for STAC module errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class STACValidationError(STACError):
    """Raised when data validation fails."""
    pass


class STACDatabaseError(STACError):
    """Raised when database operations fail."""
    pass


class STACAPIError(STACError):
    """Raised when API operations fail."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, 
                 response_data: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data or {}


class STACAuthenticationError(STACAPIError):
    """Raised when authentication fails."""
    pass


class STACRateLimitError(STACAPIError):
    """Raised when rate limits are exceeded."""
    pass


class STACOptimizationError(STACError):
    """Raised when optimization operations fail."""
    pass


class STACConfigurationError(STACError):
    """Raised when configuration is invalid."""
    pass