"""
Health controller - provides health check endpoints.
"""

from flask import Blueprint, jsonify


class HealthController:
    """Controller for health check endpoints."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def register_routes(self, app):
        """Register health routes."""
        bp = Blueprint('health', __name__)

        @bp.route('/health', methods=['GET'])
        def health_check():
            """Basic health check."""
            return jsonify({
                'status': 'healthy',
                'service': 'scc-api'
            }), 200

        @bp.route('/health/detailed', methods=['GET'])
        def detailed_health():
            """Detailed health check including dependencies."""
            health = {
                'status': 'healthy',
                'checks': {
                    'database': self._check_database(),
                    'samba': self._check_samba()
                }
            }

            # If any check fails, overall status is unhealthy
            if not all(check['healthy'] for check in health['checks'].values()):
                health['status'] = 'unhealthy'

            status_code = 200 if health['status'] == 'healthy' else 503
            return jsonify(health), status_code

        app.register_blueprint(bp)

    def _check_database(self) -> dict:
        """Check database connectivity."""
        try:
            import sqlite3
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
            return {'healthy': True, 'message': 'Database OK'}
        except Exception as e:
            return {'healthy': False, 'message': str(e)}

    def _check_samba(self) -> dict:
        """Check Samba service status."""
        try:
            import subprocess
            result = subprocess.run(['systemctl', 'is-active', 'smbd'],
                                  capture_output=True, text=True, timeout=5)
            healthy = result.returncode == 0 and result.stdout.strip() == 'active'
            return {
                'healthy': healthy,
                'message': 'Samba OK' if healthy else 'Samba not active'
            }
        except Exception as e:
            return {'healthy': False, 'message': str(e)}