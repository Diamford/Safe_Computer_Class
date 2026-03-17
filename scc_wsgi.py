#!/usr/bin/env python3
"""
WSGI application wrapper for Safe Computer Class HTTP API.

Enables running scc.py with production WSGI servers like gunicorn, uWSGI, etc.

Usage with gunicorn:
    gunicorn --bind 0.0.0.0:80 --workers 4 scc_wsgi:app
"""

import json
import os
import sys
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs

# Make sure we can import scc module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scc import SchoolSamba, SCCRequestHandler


# Global instance - initialized once
_school_instance = None


def get_school_instance():
    """Get or create the SchoolSamba instance."""
    global _school_instance
    if _school_instance is None:
        _school_instance = SchoolSamba()
        SCCRequestHandler.school = _school_instance
    return _school_instance


class WSGIHandler:
    """
    WSGI-compatible HTTP request handler for Safe Computer Class.
    
    Converts WSGI environ/start_response to our HTTP JSON API.
    """
    
    def __init__(self, environ, start_response):
        self.environ = environ
        self.start_response = start_response
        self.school = get_school_instance()
    
    def handle_request(self):
        """Process the WSGI request."""
        method = self.environ.get('REQUEST_METHOD', 'GET')
        path = self.environ.get('PATH_INFO', '/')
        
        # Only POST requests are supported for API endpoints
        if method != 'POST':
            return self._send_json(405, {'ok': False, 'message': 'method not allowed'})
        
        # Read request body
        try:
            content_length = int(self.environ.get('CONTENT_LENGTH', 0) or 0)
            body = self.environ['wsgi.input'].read(content_length)
            data = json.loads(body.decode('utf-8') or '{}') if body else {}
        except Exception:
            return self._send_json(400, {'ok': False, 'message': 'invalid request'})
        
        # Route requests
        if path == '/api/scc/register_card':
            return self._handle_register_card(data)
        elif path == '/api/scc/verify_card':
            return self._handle_verify_card(data)
        elif path == '/api/scc/verify_pin':
            return self._handle_verify_pin(data)
        elif path == '/api/scc/auth':
            return self._handle_auth(data)
        else:
            return self._send_json(404, {'ok': False, 'message': 'not found'})
    
    def _handle_register_card(self, data):
        """Handle card registration."""
        username = str(data.get('username', '')).strip()
        card_hash = str(data.get('card_hash', '')).strip()
        pin_hash = str(data.get('pin_hash', '')).strip()
        
        if not username or not card_hash or not pin_hash:
            return self._send_json(400, {'ok': False, 'message': 'missing fields'})
        
        ok, msg = self.school.register_card(username, card_hash, pin_hash)
        return self._send_json(200 if ok else 400, {'ok': ok, 'message': msg})
    
    def _handle_verify_card(self, data):
        """Handle card verification."""
        card_hash = str(data.get('card_hash', '')).strip()
        if not card_hash:
            return self._send_json(400, {'exists': False, 'require_pin': False})
        
        exists, require_pin = self.school.verify_card(card_hash)
        return self._send_json(200, {'exists': exists, 'require_pin': require_pin})
    
    def _handle_verify_pin(self, data):
        """Handle PIN verification."""
        card_hash = str(data.get('card_hash', '')).strip()
        pin_hash = str(data.get('pin_hash', '')).strip()
        
        if not card_hash or not pin_hash:
            return self._send_json(400, {'ok': False})
        
        ok = self.school.verify_pin(card_hash, pin_hash)
        return self._send_json(200, {'ok': ok})
    
    def _handle_auth(self, data):
        """Handle authentication (UUID + PIN)."""
        uuid = str(data.get('uuid', '')).strip() or str(data.get('card_hash', '')).strip()
        pin_hash = str(data.get('pin_hash', '')).strip()
        
        ok, payload = self.school.auth_uuid_pin(uuid, pin_hash)
        if ok:
            return self._send_json(200, {'ok': True, **payload})
        else:
            return self._send_json(200, {'ok': False})
    
    def _send_json(self, status_code, data):
        """Send JSON response."""
        body = json.dumps(data).encode('utf-8')
        status_text = {
            200: 'OK',
            400: 'Bad Request',
            404: 'Not Found',
            405: 'Method Not Allowed',
            500: 'Internal Server Error',
        }.get(status_code, 'Unknown')
        
        self.start_response(
            f'{status_code} {status_text}',
            [
                ('Content-Type', 'application/json; charset=utf-8'),
                ('Content-Length', str(len(body))),
            ]
        )
        return [body]


def app(environ, start_response):
    """
    WSGI application entry point.
    
    This is the function that gunicorn/uWSGI will call.
    """
    try:
        handler = WSGIHandler(environ, start_response)
        return handler.handle_request()
    except Exception as e:
        print(f"Error in WSGI app: {e}", file=sys.stderr)
        start_response('500 Internal Server Error', [
            ('Content-Type', 'application/json; charset=utf-8'),
        ])
        return [json.dumps({'ok': False, 'message': 'internal error'}).encode('utf-8')]


if __name__ == '__main__':
    # For testing locally with gunicorn
    print("Starting SCC WSGI app with gunicorn...")
    print("Run: gunicorn --bind 0.0.0.0:80 --workers 4 scc_wsgi:app")
