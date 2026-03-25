"""
Authentication rules - domain logic for auth processes.
"""

import hashlib
from typing import Optional
from ..entities import Card
from ..exceptions import InvalidPinError


class AuthRules:
    """Domain rules for authentication."""

    @staticmethod
    def hash_pin(pin: str, salt: str = "") -> str:
        """Hash a PIN with optional salt."""
        return hashlib.sha256(f"{pin}{salt}".encode()).hexdigest()

    @staticmethod
    def verify_pin(card: Card, provided_pin: str) -> bool:
        """Verify a provided PIN against stored hash."""
        if not card.pin_hash:
            return False
        hashed_pin = AuthRules.hash_pin(provided_pin)
        return hashed_pin == card.pin_hash

    @staticmethod
    def hash_card_uid(uid: str, salt: str = "SCC_SALT") -> str:
        """Hash RFID card UID with salt."""
        return hashlib.sha256(f"{uid}{salt}".encode()).hexdigest()