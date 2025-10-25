"""
Custom exceptions for the RCV Votes application.
"""

from typing import Optional


class RCVError(Exception):
    """Base exception for RCV Votes application."""
    pass


class APIError(RCVError):
    """Raised when Congress.gov API operations fail."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class ValidationError(RCVError):
    """Raised when data validation fails."""
    
    def __init__(self, message: str, field_name: Optional[str] = None, invalid_value: Optional[str] = None):
        super().__init__(message)
        self.field_name = field_name
        self.invalid_value = invalid_value


class ScrapingError(RCVError):
    """Raised when web scraping operations fail."""
    pass


class ConfigurationError(RCVError):
    """Raised when configuration is invalid or missing."""
    pass
