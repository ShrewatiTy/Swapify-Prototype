import json
import os
import pathlib
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from urllib.request import Request, urlopen

PORT = int(os.environ.get("PORT", "3000"))
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")
ROOT_DIR = pathlib.Path(__file__).resolve().parent

MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".txt": "text/plain; charset=utf-8",
    ".pdf": "application/pdf",
}


class SwapifyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", ""):
            self.serve_file(ROOT_DIR / "index.html")
            return

        requested_path = parsed.path.lstrip("/")
        candidate = (ROOT_DIR / requested_path).resolve()
        if candidate.exists() and candidate.is_file() and ROOT_DIR in candidate.parents:
            self.serve_file(candidate)
            return

        self.serve_file(ROOT_DIR / "index.html")

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/ai":
            self.send_response(404)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Not found"}).encode("utf-8"))
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length) if content_length else b"{}"
        try:
            payload = json.loads(raw_body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self.send_json(400, {"error": "Invalid JSON body."})
            return

        query = payload.get("query", "")
        if not isinstance(query, str) or not query.strip():
            self.send_json(400, {"error": "Please provide a query."})
            return

        if not GEMINI_API_KEY:
            self.send_json(500, {"error": "Set GEMINI_API_KEY before starting the server."})
            return

        body = json.dumps({
            "contents": [{"role": "user", "parts": [{"text": query}]}],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 500,
            },
        }).encode("utf-8")

        request = Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        try:
            with urlopen(request, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8") or "{}")
        except Exception as exc:  # pragma: no cover - network path
            self.send_json(502, {"error": f"Unable to reach the Gemini API: {exc}"})
            return

        reply = None
        try:
            reply = "\n".join(
                part.get("text", "")
                for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                if part.get("text")
            ).strip()
        except Exception:
            reply = None

        self.send_json(200, {"reply": reply or "I could not generate a response right now."})

    def send_json(self, status_code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_file(self, file_path):
        extension = file_path.suffix.lower()
        content_type = MIME_TYPES.get(extension, "application/octet-stream")
        try:
            data = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Not found")


if __name__ == "__main__":
    print(f"Swapify AI backend is running at http://localhost:{PORT}")
    print("Set GEMINI_API_KEY before starting if you want live Gemini replies.")
    server = ThreadingHTTPServer(("0.0.0.0", PORT), SwapifyHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        server.server_close()
        sys.exit(0)
