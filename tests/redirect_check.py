"""Run actual HTTP adapters against a local redirect to a different hostname."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import tempfile
import threading
import time

from dashboard.server import App


class Redirect(BaseHTTPRequestHandler):
    outside = []

    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.headers.get("Host", "").startswith("localhost:"):
            self.outside.append(self.path)
            self.send_response(200)
            self.end_headers()
            return
        self.send_response(302)
        self.send_header("Location", f"http://localhost:{self.server.server_port}/out-of-scope")
        self.send_header("Content-Length", "0")
        self.end_headers()


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Redirect)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory() as data:
            app = App(data)
            try:
                e = app.save_engagement(dict(name="Redirect lab", scope="127.0.0.1", excluded="", authorized=True, duration=10, rate=10))
                for tool in ("httpx", "katana", "feroxbuster", "ffuf", "nuclei"):
                    if not any(t["name"] == tool and t["installed"] for t in app.tools()):
                        continue
                    job = app.enqueue(dict(engagement_id=e["id"], tool=tool, target=f"http://127.0.0.1:{server.server_port}"))
                    deadline = time.monotonic() + 15
                    while time.monotonic() < deadline:
                        result = app.get("job", job["id"])
                        if result["status"] not in ("queued", "running", "cancelling"):
                            break
                        time.sleep(.1)
                    assert result["status"] in ("completed", "timed_out"), result
                    assert not Redirect.outside, f"{tool} followed an out-of-scope redirect"
                    print("PASS", tool, "did not follow cross-host redirect", flush=True)
            finally:
                app.shutdown()
                app.db.close()
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
