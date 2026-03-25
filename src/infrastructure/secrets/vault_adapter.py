"""
Secrets adapter - handles secure storage of sensitive data.
"""

import os
from abc import ABC, abstractmethod
from typing import Optional


class SecretsProvider(ABC):
    @abstractmethod
    def get_secret(self, key: str) -> Optional[str]:
        pass

    @abstractmethod
    def set_secret(self, key: str, value: str) -> None:
        pass


class EnvironmentSecretsProvider(SecretsProvider):
    """Simple environment-based secrets provider for development."""

    def get_secret(self, key: str) -> Optional[str]:
        return os.getenv(key)

    def set_secret(self, key: str, value: str) -> None:
        os.environ[key] = value


class VaultSecretsProvider(SecretsProvider):
    """HashiCorp Vault-based secrets provider for production."""

    def __init__(self, vault_addr: str, token: str):
        self.vault_addr = vault_addr
        self.token = token
        # In real implementation, use hvac library
        # self.client = hvac.Client(url=vault_addr, token=token)

    def get_secret(self, key: str) -> Optional[str]:
        # Simplified - would use actual Vault API
        return os.getenv(f"VAULT_{key}")

    def set_secret(self, key: str, value: str) -> None:
        # Simplified - would use actual Vault API
        os.environ[f"VAULT_{key}"] = value