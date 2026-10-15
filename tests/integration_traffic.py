"""Actual httpx/Katana throttling checks against a temporary local HTTP 429 fixture."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import tempfile
import threading
import time

from dashboard.server import App


class Throttle(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        body = b"Local fixture rate limit"
        self.send_response(429)
        self.send_header("Retry-After", "3")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Throttle)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory() as directory:
            app = App(directory)
            try:
                for tool in ("httpx", "katana"):
                    if not any(t["name"] == tool and t["runnable"] for t in app.tools()):
                        continue
                    e = app.save_engagement(dict(name="Local throttle fixture " + tool, scope="127.0.0.1", authorized=True,
                                                 duration=20, traffic={"cooldown": 1}))
                    job = app.enqueue(dict(engagement_id=e["id"], tool=tool, target=f"http://127.0.0.1:{server.server_port}"))
                    deadline = time.monotonic() + 25
                    while time.monotonic() < deadline:
                        result = app.get("job", job["id"])
                        if result["status"] not in ("queued", "running", "cancelling"):
                            break
                        time.sleep(.05)
                    assert result["status"] == "rate_limited", result
                    assert result["traffic_events"][0]["delay"] == 3, (result, app.logpath(job).read_text())
                    assert app.traffic_gate(result), "No origin cooldown was recorded"
                    print("PASS", tool, "stopped on 429 and honored Retry-After", flush=True)
            finally:
                app.shutdown()
                app.db.close()
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
