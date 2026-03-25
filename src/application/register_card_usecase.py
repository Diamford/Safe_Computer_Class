"""
Register card use case - handles card registration.
"""

from ..domain.entities import Card
from ..domain.services.auth_rules import AuthRules
from ..domain.exceptions import CardAlreadyRegisteredError, UserNotFoundError


class RegisterCardUseCase:
    """Use case for registering a new RFID card."""

    def __init__(self, user_repository, card_repository):
        self.user_repository = user_repository
        self.card_repository = card_repository

    def execute(self, username: str, card_hash: str, pin: str) -> Card:
        """
        Register a new card for a user.
        1. Verify user exists
        2. Check card not already registered
        3. Hash the PIN
        4. Save the card
        """

        # Verify user exists
        user = self.user_repository.find_by_username(username)
        if not user:
            raise UserNotFoundError(f"User {username} not found")

        # Check card not already registered
        existing_card = self.card_repository.find_by_card_hash(card_hash)
        if existing_card:
            raise CardAlreadyRegisteredError(f"Card {card_hash} already registered")

        # Hash PIN
        pin_hash = AuthRules.hash_pin(pin)

        # Create and save card
        card = Card(card_hash=card_hash, username=username, pin_hash=pin_hash)
        self.card_repository.save(card)

        return card