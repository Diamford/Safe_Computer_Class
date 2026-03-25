"""
Auth controller - handles HTTP requests for authentication.
"""

from flask import Blueprint, request, jsonify
from ...application.auth_usecase import AuthenticateUserUseCase
from ...application.register_card_usecase import RegisterCardUseCase
from ...domain.exceptions import DomainError


class AuthController:
    """HTTP controller for authentication endpoints."""

    def __init__(self, auth_usecase: AuthenticateUserUseCase, register_usecase: RegisterCardUseCase):
        self.auth_usecase = auth_usecase
        self.register_usecase = register_usecase

    def register_routes(self, app):
        """Register routes with Flask app."""
        bp = Blueprint('auth', __name__)

        @bp.route('/api/scc/register_card', methods=['POST'])
        def register_card():
            try:
                data = request.get_json()
                username = data['username']
                card_hash = data['card_hash']
                pin = data['pin']

                card = self.register_usecase.execute(username, card_hash, pin)
                return jsonify({'success': True, 'message': 'Card registered'}), 201

            except DomainError as e:
                return jsonify({'success': False, 'message': str(e)}), 400
            except Exception as e:
                return jsonify({'success': False, 'message': 'Internal error'}), 500

        @bp.route('/api/scc/verify_card', methods=['POST'])
        def verify_card():
            try:
                data = request.get_json()
                card_hash = data['card_hash']

                # For now, just check if card exists
                # In full implementation, this would be a separate use case
                card = self.auth_usecase.card_repository.find_by_card_hash(card_hash)
                exists = card is not None
                require_pin = exists and card.has_pin()

                return jsonify({
                    'exists': exists,
                    'require_pin': require_pin
                }), 200

            except Exception as e:
                return jsonify({'exists': False, 'require_pin': False}), 500

        @bp.route('/api/scc/auth', methods=['POST'])
        def auth():
            try:
                data = request.get_json()
                card_hash = data.get('uuid') or data.get('card_hash')
                pin_hash = data.get('pin_hash')  # Note: this should be plain PIN, not hash

                result = self.auth_usecase.execute(card_hash, pin_hash)

                return jsonify({
                    'server': result.server,
                    'username': result.user.username,
                    'drive_letter': result.drive_letter,
                    'password': result.password,
                    'success': result.success
                }), 200

            except DomainError as e:
                return jsonify({'success': False, 'message': str(e)}), 401
            except Exception as e:
                return jsonify({'success': False, 'message': 'Internal error'}), 500

        app.register_blueprint(bp)