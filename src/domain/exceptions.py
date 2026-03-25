"""
Domain-specific exceptions for Safe Computer Class system.
"""

class DomainError(Exception):
    """Base class for domain errors."""
    pass


class UserNotFoundError(DomainError):
    """Raised when a user is not found."""
    pass


class CardNotFoundError(DomainError):
    """Raised when an RFID card is not found."""
    pass


class InvalidPinError(DomainError):
    """Raised when PIN verification fails."""
    pass


class PermissionDeniedError(DomainError):
    """Raised when user lacks permission for an operation."""
    pass


class CardAlreadyRegisteredError(DomainError):
    """Raised when trying to register an already registered card."""
    pass


class InvalidRoleError(DomainError):
    """Raised when an invalid role is specified."""
    pass