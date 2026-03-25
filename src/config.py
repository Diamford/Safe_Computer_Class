"""
Configuration management for the application.
"""

import os
from typing import Dict, Any


class Config:
    """Application configuration."""

    def __init__(self):
        self._config = {}

    def load_from_env(self) -> Dict[str, Any]:
        """Load configuration from environment variables."""
        self._config = {
            'DATABASE_PATH': os.getenv('SCC_DATABASE_PATH', '/srv/samba/school.db'),
            'HOST': os.getenv('SCC_HOST', '0.0.0.0'),
            'PORT': int(os.getenv('SCC_PORT', '80')),
            'DEBUG': os.getenv('SCC_DEBUG', 'False').lower() == 'true',
            'SECRET_KEY': os.getenv('SCC_SECRET_KEY', 'dev-secret-key'),
            'SAMBA_CONFIG_PATH': os.getenv('SCC_SAMBA_CONFIG', '/etc/samba/smb.conf'),
            'VAULT_ADDR': os.getenv('VAULT_ADDR'),
            'VAULT_TOKEN': os.getenv('VAULT_TOKEN'),
        }
        return self._config

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return self._config.get(key, default)

    @property
    def database_path(self) -> str:
        return self._config.get('DATABASE_PATH', '/srv/samba/school.db')

    @property
    def host(self) -> str:
        return self._config.get('HOST', '0.0.0.0')

    @property
    def port(self) -> int:
        return self._config.get('PORT', 80)

    @property
    def debug(self) -> bool:
        return self._config.get('DEBUG', False)


# Global config instance
config = Config()