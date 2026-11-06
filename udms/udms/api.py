"""REST API. Authenticate with the X-API-Key header.

GET  /health
GET  /entities/<entity>?q=text&limit=50&offset=0
GET  /entities/<entity>/<id>
PUT  /entities/<entity>/<id>      (JSON body of fields to change)
GET  /quality
GET  /audit
"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .service import DataService, NotFound, PermissionDenied


def _int(qs, key, default, lo, hi):
    try:
        return max(lo, min(hi, int(qs.get(key, [default])[0])))
    except ValueError:
        return default


def make_handler(service: DataService):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, payload):
            body = json.dumps(payload, indent=2).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _handle(self, method):
            url = urlparse(self.path)
            parts = [p for p in url.path.split("/") if p]
            qs = parse_qs(url.query)
            if parts == ["health"]:
                return self._send(200, {"status": "ok"})

            user = service.authenticate(self.headers.get("X-API-Key"))
            if user is None:
                return self._send(401, {"error": "missing or invalid X-API-Key"})
            try:
                if method == "GET" and parts == ["quality"]:
                    return self._send(200, service.quality_report(user))
                if method == "GET" and parts == ["audit"]:
                    return self._send(200, service.audit_log(user))
                if parts[:1] == ["entities"] and len(parts) == 2 and method == "GET":
                    return self._send(200, service.list(
                        user, parts[1], qs.get("q", [None])[0],
                        _int(qs, "limit", 50, 1, 500), _int(qs, "offset", 0, 0, 10**9)))
                if parts[:1] == ["entities"] and len(parts) == 3:
                    if method == "GET":
                        return self._send(200, service.get(user, parts[1], parts[2]))
                    if method == "PUT":
                        length = int(self.headers.get("Content-Length", 0))
                        changes = json.loads(self.rfile.read(length) or b"{}")
                        return self._send(200, service.update(user, parts[1], parts[2], changes))
                self._send(404, {"error": "not found"})
            except PermissionDenied as exc:
                self._send(403, {"error": str(exc)})
            except NotFound as exc:
                self._send(404, {"error": str(exc)})
            except (ValueError, json.JSONDecodeError) as exc:
                self._send(400, {"error": str(exc)})

        def do_GET(self):  # noqa: N802
            self._handle("GET")

        def do_PUT(self):  # noqa: N802
            self._handle("PUT")

        def log_message(self, fmt, *args):
            print(f"[api] {self.address_string()} {fmt % args}")

    return Handler


def serve(service: DataService, host: str, port: int) -> None:
    server = ThreadingHTTPServer((host, port), make_handler(service))
    print(f"UDMS API on http://{host}:{port}  (send X-API-Key header; Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
