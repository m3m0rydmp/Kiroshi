"""Opt-in integration checks: actual installed binaries against a loopback fixture only.

Run: python3 -m tests.integration_local
No public targets, DNS discovery, or external agent APIs are used.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import tempfile
import threading
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from dashboard.server import App, Handler
from dashboard.http_identity import browser_user_agent


class Fixture(BaseHTTPRequestHandler):
    seen = []
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.seen.append(dict(path=self.path, cookie=self.headers.get("Cookie"), authorization=self.headers.get("Authorization"), user_agent=self.headers.get("User-Agent")))
        if self.path.startswith("/redirect"):
            self.send_response(302)
            self.send_header("Location", "http://localhost:1/outside-scope")
            self.end_headers()
            return
        body = b'<html><title>Kiroshi lab</title><a href="/inside">Inside</a><a href="http://localhost:1/outside-scope">Outside</a></html>'
        self.send_response(200 if self.path in ("/", "/inside", "/robots.txt") else 404)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    fixture = ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
    threading.Thread(target=fixture.serve_forever, daemon=True).start()
    origin = f"http://127.0.0.1:{fixture.server_port}"
    failures = []
    with tempfile.TemporaryDirectory() as data:
        app = App(data)
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.app = app
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with urlopen(base + "/") as response:
                assert response.status == 200
            with urlopen(base + "/api/state") as response:
                state = json.load(response)
            try:
                urlopen(Request(base + "/api/engagements", data=b"{}", headers={"Content-Type": "application/json"}))
                raise AssertionError("Missing CSRF token was accepted")
            except HTTPError as exc:
                assert exc.code == 403
            try:
                urlopen(Request(base + "/api/state", headers={"Host": "evil.test"}))
                raise AssertionError("Untrusted host was accepted")
            except HTTPError as exc:
                assert exc.code == 403
            print("PASS HTTP UI/API, request-token and Host protections")
            e = app.save_engagement(dict(name="Loopback fixture", scope="127.0.0.1", excluded="", authorized=True, duration=30, rate=10))
            auth = app.save_auth(dict(engagement_id=e["id"], label="Account A", origin=origin, cookie="kiroshi_session=local-secret", headers="Authorization: Bearer local-only-token"))
            installed = {tool["name"] for tool in app.tools() if tool["installed"]}
            for tool in ("httpx", "katana", "feroxbuster", "ffuf", "nuclei"):
                selected_tools = os.environ.get("KIROSHI_TEST_TOOLS", "").split(",")
                if selected_tools != [""] and tool not in selected_tools:
                    continue
                if tool not in installed:
                    print("SKIP", tool, "not installed")
                    continue
                for authenticated in (False, True):
                    before = len(Fixture.seen)
                    job = app.enqueue(dict(engagement_id=e["id"], tool=tool, target=origin, auth_id=auth["id"] if authenticated else "", diagnostics=os.environ.get("KIROSHI_TEST_DIAGNOSTICS") == "1"))
                    deadline = time.monotonic() + 35
                    while time.monotonic() < deadline:
                        result = app.get("job", job["id"])
                        if result["status"] not in ("queued", "running", "cancelling"):
                            break
                        time.sleep(.1)
                    seen = Fixture.seen[before:]
                    ok = result["status"] == "completed" and bool(seen)
                    ok = ok and all(row["user_agent"] == browser_user_agent() for row in seen)
                    if authenticated:
                        ok = ok and all(row["cookie"] == "kiroshi_session=local-secret" and row["authorization"] == "Bearer local-only-token" for row in seen)
                    else:
                        ok = ok and all(row["cookie"] is None and row["authorization"] is None for row in seen)
                    log = app.logpath(job).read_text() if app.logpath(job).exists() else ""
                    ok = ok and "local-secret" not in log and "local-only-token" not in log
                    print("PASS" if ok else "FAIL", tool, "session" if authenticated else "anonymous", result["status"], len(seen), "requests")
                    if not ok:
                        failures.append((tool, authenticated, result, log[-2500:]))
            if any(j["tool"] in ("httpx", "katana", "nuclei") for j in app.all("job")):
                assert app.all("asset"), "No normalized cache entries"
            assert len({job["identity"] for job in app.all("job")}) == 2
            print("PASS separate run identities;", len(app.all("asset")), "normalized cached assets")
        finally:
            app.shutdown()
            server.shutdown()
            server.server_close()
            app.db.close()
    fixture.shutdown()
    fixture.server_close()
    for tool, authenticated, result, output in failures:
        print(json.dumps(dict(tool=tool, authenticated=authenticated, status=result["status"], error=result.get("error"), output=output), indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
