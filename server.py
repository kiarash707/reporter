import base64
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BOT_INTERNAL_URL = os.getenv("BOT_INTERNAL_URL", "http://reporter.railway.internal:8080").rstrip("/")
MONITOR_TOKEN = os.getenv("MONITOR_TOKEN", "")
DASHBOARD_USER = os.getenv("DASHBOARD_USER", "admin")
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "")
PORT = int(os.getenv("PORT", "8080"))

with open(os.path.join(os.path.dirname(__file__), "index.html"), "r", encoding="utf-8") as f:
    INDEX_HTML = f.read()


def bot_request(path, timeout=4):
    if not MONITOR_TOKEN:
        raise RuntimeError("MONITOR_TOKEN is not configured")

    request = Request(
        f"{BOT_INTERNAL_URL}{path}",
        headers={
            "X-Monitor-Token": MONITOR_TOKEN,
            "User-Agent": "ReporterDashboard/1.0"
        },
        method="GET"
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def authorized(handler):
    if not DASHBOARD_PASSWORD:
        return True

    header = handler.headers.get("Authorization", "")
    if not header.startswith("Basic "):
        handler.send_response(401)
        handler.send_header("WWW-Authenticate", 'Basic realm="Reporter Dashboard"')
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
        handler.end_headers()
        return False

    return True


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "ReporterDashboard/1.0"

    def send_json(self, status_code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, html):
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not authorized(self):
            return

        try:
            parsed = urlparse(self.path)

            if parsed.path == "/":
                self.send_html(INDEX_HTML)
                return

            if parsed.path == "/health":
                self.send_json(200, {"status": "ok", "service": "reporter-dashboard"})
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

            self.send_json(404, {"error": "not_found"})
        except Exception as exc:
            self.send_json(500, {"error": str(exc)[:180]})

    def log_message(self, format, *args):
        return


def main():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), DashboardHandler)
    print(f"Reporter Dashboard listening on port {PORT}")
    print(f"Bot internal endpoint: {BOT_INTERNAL_URL}")
    server.serve_forever()


if __name__ == "__main__":
    main()
