"""
Main API application using Flask.
"""

from flask import Flask
from ..infrastructure.db.repository import SQLiteUserRepository, SQLiteCardRepository, SQLiteMountRepository
from ..infrastructure.samba.samba_adapter import SambaAdapter
from ..infrastructure.secrets.vault_adapter import EnvironmentSecretsProvider
from ..application.auth_usecase import AuthenticateUserUseCase
from ..application.register_card_usecase import RegisterCardUseCase
from ..application.mount_usecase import SetupMountsUseCase
from .controllers.auth_controller import AuthController
from .controllers.health_controller import HealthController


def create_app(config: dict) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)

    # Initialize infrastructure
    db_path = config.get('DATABASE_PATH', '/srv/samba/school.db')
    user_repo = SQLiteUserRepository(db_path)
    card_repo = SQLiteCardRepository(db_path)
    mount_repo = SQLiteMountRepository(db_path)
    samba_adapter = SambaAdapter()
    secrets_provider = EnvironmentSecretsProvider()

    # Initialize use cases
    auth_usecase = AuthenticateUserUseCase(user_repo, card_repo)
    register_usecase = RegisterCardUseCase(user_repo, card_repo)
    mount_usecase = SetupMountsUseCase(mount_repo, samba_adapter)

    # Initialize controllers
    auth_controller = AuthController(auth_usecase, register_usecase)
    health_controller = HealthController(db_path)

    # Register routes
    auth_controller.register_routes(app)
    health_controller.register_routes(app)

    return app


if __name__ == '__main__':
    # For development
    config = {
        'DATABASE_PATH': 'school.db'
    }
    app = create_app(config)
    app.run(host='0.0.0.0', port=5000, debug=True)