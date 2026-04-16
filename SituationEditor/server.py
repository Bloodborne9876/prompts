"""
SituationEditor local HTTP server
Serves index.html and proxies danbooru.csv from the tag complete extension.
"""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

PORT = 8765
SERVE_DIR = Path(__file__).parent
CSV_PATH = Path(r"C:\sd-webui-forge-neo\extensions\a1111-sd-webui-tagcomplete\tags\danbooru.csv")


class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        parsed = urlparse(self.path)
        route = parsed.path

        try:
            if route in ("/", "/index.html"):
                self._serve_file(SERVE_DIR / "index.html", "text/html; charset=utf-8")

            elif route == "/danbooru.csv":
                if not CSV_PATH.exists():
                    self.send_error(404, f"danbooru.csv not found at {CSV_PATH}")
                    return
                self._serve_file(CSV_PATH, "text/plain; charset=utf-8")

            elif route == "/load":
                params = parse_qs(parsed.query)
                if "path" not in params:
                    self.send_error(400, "Missing 'path' parameter")
                    return
                json_path = Path(unquote(params["path"][0]))
                if not json_path.exists():
                    self.send_error(404, f"File not found: {json_path}")
                    return
                data = json_path.read_text(encoding="utf-8")
                self._send_text(200, data, "application/json; charset=utf-8")

            else:
                self.send_error(404)

        except Exception as e:
            self.send_error(500, str(e))

    def _serve_file(self, path: Path, content_type: str):
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def _send_text(self, status: int, text: str, content_type: str):
        data = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        # Suppress per-request log noise
        pass


if __name__ == "__main__":
    print(f"SituationEditor running at http://localhost:{PORT}")
    print(f"Serving from: {SERVE_DIR}")
    print(f"danbooru.csv: {CSV_PATH}")
    print(f"CSV exists: {CSV_PATH.exists()}")
    print("Press Ctrl+C to stop.\n")

    with HTTPServer(("localhost", PORT), Handler) as server:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")
