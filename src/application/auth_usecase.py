"""
Authentication use case - orchestrates the auth process.
"""

from typing import Optional
from ..domain.entities import User, Card, AuthResult
from ..domain.exceptions import CardNotFoundError, InvalidPinError, UserNotFoundError
from ..domain.services.auth_rules import AuthRules
from ..domain.services.permission_service import PermissionService


class AuthenticateUserUseCase:
    """Use case for authenticating a user with card and PIN."""

    def __init__(self, user_repository, card_repository):
        self.user_repository = user_repository
        self.card_repository = card_repository

    def execute(self, card_hash: str, pin: Optional[str] = None,
                server: str = "localhost", drive_letter: str = "Z:") -> AuthResult:
        """
        Execute authentication flow:
        1. Find card by hash
        2. If PIN required, verify PIN
        3. Get user from card
        4. Return auth result with mount info
        """

        # Find card
        card = self.card_repository.find_by_card_hash(card_hash)
        if not card:
            raise CardNotFoundError(f"Card with hash {card_hash} not found")

        # Check if PIN is required and provided
        if card.has_pin():
            if not pin:
                return AuthResult(
                    user=None, server=server, drive_letter=drive_letter,
                    success=False, message="PIN required"
                )
            if not AuthRules.verify_pin(card, pin):
                raise InvalidPinError("Invalid PIN")

        # Get user
        user = self.user_repository.find_by_username(card.username)
        if not user:
            raise UserNotFoundError(f"User {card.username} not found")

        # Get mount paths for user
        mount_paths = PermissionService.get_user_mounts(user)

        return AuthResult(
            user=user,
            server=server,
            drive_letter=drive_letter,
            success=True,
            message=f"Authenticated as {user.username}"
        )