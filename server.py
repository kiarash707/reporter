import base64
import json
import os
import time
import http.client
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BOT_INTERNAL_URL = os.getenv("BOT_INTERNAL_URL", "http://reporter.railway.internal:8080").rstrip("/")
MONITOR_TOKEN = os.getenv("MONITOR_TOKEN", "")
DASHBOARD_USER = os.getenv("DASHBOARD_USER", "admin")
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "")
PORT = int(os.getenv("PORT", "8080"))
REQUEST_TIMEOUT = max(2, min(20, int(os.getenv("REQUEST_TIMEOUT", "8"))))

# The dashboard is a private operations console; browsers should never cache its data.
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains"
}

with open(os.path.join(os.path.dirname(__file__), "index.html"), "r", encoding="utf-8") as f:
    INDEX_HTML = f.read()


def bot_request(path, timeout=4, method="GET", payload=None):
    if not MONITOR_TOKEN:
        raise RuntimeError("MONITOR_TOKEN is not configured")
    request = Request(
        f"{BOT_INTERNAL_URL}{path}",
        headers={
            "X-Monitor-Token": MONITOR_TOKEN,
            "User-Agent": "ReporterDashboard/4.1"
        },
        method=method
    )
    if payload is not None:
        request.data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request.add_header("Content-Type", "application/json; charset=utf-8")
    with urlopen(request, timeout=min(timeout, REQUEST_TIMEOUT)) as response:
        return json.loads(response.read().decode("utf-8"))


def _bot_http_target():
    parsed = urlparse(BOT_INTERNAL_URL)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise RuntimeError("BOT_INTERNAL_URL is invalid")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return parsed, port


def bot_upload_file(path, content_length, query=""):
    if not MONITOR_TOKEN:
        raise RuntimeError("MONITOR_TOKEN is not configured")
    parsed, port = _bot_http_target()
    connection_cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    conn = connection_cls(parsed.hostname, port, timeout=180)
    target = parsed.path.rstrip("/") + "/api/backup/restore" + (("?" + query) if query else "")
    try:
        conn.putrequest("POST", target)
        conn.putheader("Host", parsed.hostname)
        conn.putheader("X-Monitor-Token", MONITOR_TOKEN)
        conn.putheader("User-Agent", "ReporterDashboard/4.1")
        conn.putheader("Content-Type", "application/zip")
        conn.putheader("Content-Length", str(content_length))
        conn.endheaders()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                conn.send(chunk)
        response = conn.getresponse()
        return response.status, response.read()
    finally:
        conn.close()


def bot_open_download(path, timeout=180):
    if not MONITOR_TOKEN:
        raise RuntimeError("MONITOR_TOKEN is not configured")
    request = Request(
        f"{BOT_INTERNAL_URL}{path}",
        headers={
            "X-Monitor-Token": MONITOR_TOKEN,
            "User-Agent": "ReporterDashboard/4.1"
        },
        method="GET",
    )
    return urlopen(request, timeout=timeout)

def authorized(handler):
    if not DASHBOARD_PASSWORD:
        return True

    header = handler.headers.get("Authorization", "")
    if not header.startswith("Basic "):
        handler.send_response(401)
        handler.send_header("WWW-Authenticate", 'Basic realm="Reporter Dashboard"')
        handler.send_header("Cache-Control", "no-store")
        handler.send_header("X-Content-Type-Options", "nosniff")
        handler.end_headers()
        return False

    try:
        decoded = base64.b64decode(header[6:]).decode("utf-8")
        username, password = decoded.split(":", 1)
    except Exception:
        username, password = "", ""

    if username != DASHBOARD_USER or password != DASHBOARD_PASSWORD:
        handler.send_response(401)
        handler.send_header("WWW-Authenticate", 'Basic realm="Reporter Dashboard"')
        handler.send_header("Cache-Control", "no-store")
        handler.send_header("X-Content-Type-Options", "nosniff")
        handler.end_headers()
        return False

    return True


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "ReporterDashboard/4.1"

    def send_json(self, status_code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        for key, value in SECURITY_HEADERS.items():
            self.send_header(key, value)
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'self'")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, html):
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        for key, value in SECURITY_HEADERS.items():
            self.send_header(key, value)
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'self'")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        try:
            parsed = urlparse(self.path)

            # Keep a public health endpoint so Railway can monitor this service
            # without exposing dashboard data or credentials.
            if parsed.path == "/health":
                self.send_json(200, {"status": "ok", "service": "reporter-dashboard"})
                return

            if not authorized(self):
                return

            if parsed.path == "/":
                self.send_html(INDEX_HTML)
                return

            if parsed.path == "/api/users":
                params = parse_qs(parsed.query)
                safe_query = urlencode({k: v[0] for k, v in params.items() if k in ("q", "limit")})
                data = bot_request("/api/users" + (("?" + safe_query) if safe_query else ""))
                self.send_json(200, data)
                return

            if parsed.path == "/api/admins":
                self.send_json(200, bot_request("/api/admins"))
                return

            if parsed.path == "/api/channels":
                self.send_json(200, bot_request("/api/channels"))
                return

            if parsed.path == "/api/diagnostics":
                self.send_json(200, bot_request("/api/diagnostics"))
                return

            if parsed.path == "/api/status":
                try:
                    data = bot_request("/api/status")
                    self.send_json(200, {"ok": True, "bot": data, "checked_at": time.time()})
                except (HTTPError, URLError, TimeoutError, OSError, RuntimeError) as exc:
                    self.send_json(200, {
                        "ok": False,
                        "bot": {
                            "status": "offline",
                            "telegram_connected": False,
                            "error": str(exc)[:180]
                        },
                        "checked_at": time.time()
                    })
                return

            if parsed.path == "/api/logs":
                params = parse_qs(parsed.query)
                lines = params.get("lines", ["120"])[0]
                try:
                    count = max(1, min(int(lines), 300))
                except ValueError:
                    count = 120

                try:
                    data = bot_request(f"/api/logs?lines={count}")
                    self.send_json(200, {"ok": True, **data, "checked_at": time.time()})
                except Exception as exc:
                    self.send_json(200, {
                        "ok": False,
                        "lines": [f"[dashboard] Unable to reach bot monitoring API: {exc}"],
                        "checked_at": time.time()
                    })
                return

            if parsed.path == "/api/backup/info":
                self.send_json(200, {"ok": True, **bot_request("/api/backup/info", timeout=15)})
                return

            if parsed.path == "/api/backup/history":
                self.send_json(200, {"ok": True, **bot_request("/api/backup/history", timeout=15)})
                return

            if parsed.path == "/api/backup/download":
                try:
                    with bot_open_download("/api/backup/download") as upstream:
                        self.send_response(200)
                        self.send_header("Content-Type", upstream.headers.get("Content-Type", "application/zip"))
                        self.send_header("Content-Disposition", upstream.headers.get("Content-Disposition", 'attachment; filename="reporter-backup.zip"'))
                        self.send_header("Cache-Control", "no-store")
                        self.send_header("X-Content-Type-Options", "nosniff")
                        size = upstream.headers.get("Content-Length")
                        if size:
                            self.send_header("Content-Length", size)
                        self.end_headers()
                        while True:
                            chunk = upstream.read(1024 * 1024)
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    return
                return

            if parsed.path == "/api/backup/download-existing":
                params = parse_qs(parsed.query)
                name = params.get("name", [""])[0]
                if not name or "/" in name or "\\" in name or ".." in name or not name.startswith("reporter-backup-") or not name.endswith(".zip"):
                    self.send_json(400, {"ok": False, "error": "backup_name_invalid"})
                    return
                try:
                    with bot_open_download("/api/backup/download-existing?" + urlencode({"name": name})) as upstream:
                        self.send_response(200)
                        self.send_header("Content-Type", upstream.headers.get("Content-Type", "application/zip"))
                        self.send_header("Content-Disposition", upstream.headers.get("Content-Disposition", f'attachment; filename="{name}"'))
                        self.send_header("Cache-Control", "no-store")
                        self.send_header("X-Content-Type-Options", "nosniff")
                        size = upstream.headers.get("Content-Length")
                        if size:
                            self.send_header("Content-Length", size)
                        self.end_headers()
                        while True:
                            chunk = upstream.read(1024 * 1024)
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    return
                return

            self.send_json(404, {"error": "not_found"})
        except Exception as exc:
            self.send_json(500, {"error": str(exc)[:180]})

    def do_POST(self):
        try:
            parsed = urlparse(self.path)
            if not authorized(self):
                return

            try:
                content_length = int(self.headers.get("Content-Length", "0") or "0")
            except ValueError:
                content_length = 0

            if parsed.path == "/api/backup/restore":
                if content_length <= 0 or content_length > 250 * 1024 * 1024:
                    self.send_json(413, {"ok": False, "error": "backup_upload_too_large"})
                    return
                content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                if content_type not in {"application/zip", "application/octet-stream"}:
                    self.send_json(415, {"ok": False, "error": "content_type_must_be_zip"})
                    return
                self.connection.settimeout(180)
                params = parse_qs(parsed.query)
                query = urlencode({
                    "activate_source": params.get("activate_source", ["1"])[0],
                    "dry_run": params.get("dry_run", ["0"])[0],
                })
                fd, temp_path = tempfile.mkstemp(prefix="dashboard-backup-", suffix=".zip")
                os.close(fd)
                try:
                    remaining = content_length
                    with open(temp_path, "wb") as fh:
                        while remaining:
                            chunk = self.rfile.read(min(1024 * 1024, remaining))
                            if not chunk:
                                raise ConnectionError("upload ended before Content-Length")
                            fh.write(chunk)
                            remaining -= len(chunk)
                    status, body = bot_upload_file(temp_path, content_length, query=query)
                    try:
                        payload = json.loads(body.decode("utf-8") or "{}")
                    except Exception:
                        payload = {"ok": False, "error": "invalid_bot_response"}
                    self.send_json(status, payload)
                    return
                finally:
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass

            if parsed.path == "/api/backup/revert-source":
                data = bot_request("/api/backup/revert-source", timeout=20, method="POST", payload={})
                self.send_json(200, data)
                return

            if parsed.path not in ["/api/control", "/api/users", "/api/admins", "/api/channels"]:
                self.send_json(404, {"error": "not_found"})
                return
            if content_length < 0 or content_length > 64 * 1024:
                self.send_json(413, {"ok": False, "error": "request_too_large"})
                return
            raw = self.rfile.read(content_length)
            payload = json.loads(raw.decode("utf-8") or "{}") if raw else {}
            data = bot_request(parsed.path, timeout=30, method="POST", payload=payload)
            self.send_json(200, data)
        except (HTTPError, URLError, TimeoutError, OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
            self.send_json(502, {"ok": False, "error": str(exc)[:180]})
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as exc:
            try:
                self.send_json(500, {"ok": False, "error": str(exc)[:180]})
            except (BrokenPipeError, ConnectionResetError):
                pass

    def setup(self):
        super().setup()
        self.connection.settimeout(20)

    def do_HEAD(self):
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            for key, value in SECURITY_HEADERS.items():
                self.send_header(key, value)
            self.end_headers()
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        return


def main():
    ThreadingHTTPServer.allow_reuse_address = True
    ThreadingHTTPServer.daemon_threads = True
    server = ThreadingHTTPServer(("0.0.0.0", PORT), DashboardHandler)
    print(f"Reporter Dashboard listening on port {PORT}")
    print(f"Bot internal endpoint: {BOT_INTERNAL_URL}")
    server.serve_forever()


if __name__ == "__main__":
    main()
