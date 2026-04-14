from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

from .service import SchoolSamba


class SCCRequestHandler(BaseHTTPRequestHandler):
    school: "SchoolSamba | None" = None

    def _send_json(self, code: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if not SCCRequestHandler.school:
            self._send_json(500, {"ok": False, "message": "server not initialized"})
            return

        length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(length) if length > 0 else b"{}"
        try:
            data = json.loads(raw_body.decode("utf-8") or "{}")
        except Exception:
            self._send_json(400, {"ok": False, "message": "invalid JSON"})
            return

        if self.path == "/api/scc/register_card":
            username = str(data.get("username", "")).strip()
            card_hash = str(data.get("card_hash", "")).strip()
            pin_hash = str(data.get("pin_hash", "")).strip()
            if not username or not card_hash or not pin_hash:
                self._send_json(400, {"ok": False, "message": "missing fields"})
                return
            ok, msg = SCCRequestHandler.school.register_card(username, card_hash, pin_hash)
            self._send_json(200 if ok else 400, {"ok": ok, "message": msg})
            return

        if self.path == "/api/scc/verify_card":
            card_hash = str(data.get("card_hash", "")).strip()
            if not card_hash:
                self._send_json(400, {"exists": False, "require_pin": False})
                return
            exists, require_pin = SCCRequestHandler.school.verify_card(card_hash)
            self._send_json(200, {"exists": exists, "require_pin": require_pin})
            return

        if self.path == "/api/scc/verify_pin":
            card_hash = str(data.get("card_hash", "")).strip()
            pin_hash = str(data.get("pin_hash", "")).strip()
            if not card_hash or not pin_hash:
                self._send_json(400, {"ok": False})
                return
            ok = SCCRequestHandler.school.verify_pin(card_hash, pin_hash)
            self._send_json(200, {"ok": ok})
            return

        if self.path == "/api/scc/auth":
            uuid = str(data.get("uuid", "")).strip() or str(data.get("card_hash", "")).strip()
            pin_hash = str(data.get("pin_hash", "")).strip()
            ok, payload = SCCRequestHandler.school.auth_uuid_pin(uuid, pin_hash)
            self._send_json(200, {"ok": bool(ok), **(payload if ok else {})})
            return

        self._send_json(404, {"ok": False, "message": "not found"})


def run_http_server(host: str, port: int):
    school = SchoolSamba()
    SCCRequestHandler.school = school
    httpd = HTTPServer((host, port), SCCRequestHandler)
    print(f"HTTP server running on http://{host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("HTTP server stopped")
    finally:
        httpd.server_close()

