import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from dashboard.notifications import Notifications, formatted, normalize


class Receiver(BaseHTTPRequestHandler):
    seen = []

    def do_POST(self):
        self.seen.append((self.path, dict(self.headers), json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
        self.send_response(204)
        self.end_headers()

    def log_message(self, *args):
        pass


class NotificationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.service = Notifications(self.directory.name)

    def tearDown(self):
        self.service.close()
        self.directory.cleanup()

    def test_platform_detection_and_private_settings(self):
        for url, platform in (("https://discord.com/api/webhooks/123/secret-token", "discord"),
                              ("https://hooks.slack.com/services/private/token", "slack"),
                              ("https://api.telegram.org/bot123:secret-token/sendMessage?chat_id=-123", "telegram"),
                              ("https://notify.example.test/private?token=secret-token", "generic")):
            public = self.service.save(dict(url=url, enabled=True))
            self.assertEqual(public["platform"], platform)
            self.assertNotIn("secret-token", json.dumps(public))
            self.assertNotIn("url", public)
            self.assertEqual(self.service.file.stat().st_mode & 0o777, 0o600)
        self.service.save(dict(enabled=False, events=["job_completed"]))
        self.assertFalse(self.service.public()["enabled"])
        self.assertEqual(self.service.public()["events"], ["job_completed"])
        self.service.save(dict(remove=True))
        self.assertFalse(self.service.file.exists())

    def test_invalid_destinations_and_telegram_missing_chat_are_rejected(self):
        for url in ("file:///etc/passwd", "http://remote.test/hook", "https://u:pass@remote.test/hook", "https://@remote.test/hook", "https://discord.com/channels/123", "https://api.telegram.org/bot123:token/sendMessage", "https://api.telegram.org/bot123:token/sendMessage?chat_id=123&chat_id=456", "https://remote.test/#fragment"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                normalize(dict(url=url))

    def test_platform_payloads_escape_text_and_disable_mentions(self):
        event = dict(event="test", title="Owned <test>", engagement="A&B <workspace>", status="test", summary="A < B")
        discord = formatted(dict(platform="discord"), event)
        self.assertEqual(discord["allowed_mentions"], {"parse": []})
        self.assertIn("embeds", discord)
        telegram = formatted(dict(platform="telegram", chat_id="123"), event)
        self.assertIn("&lt;test&gt;", telegram["text"])
        self.assertIn("A&amp;B", telegram["text"])
        self.assertEqual(telegram["chat_id"], "123")
        slack = formatted(dict(platform="slack"), event)
        self.assertTrue(all(block["text"]["type"] == "plain_text" for block in slack["blocks"] if "text" in block))
        self.assertFalse(slack["unfurl_links"])

    def test_real_loopback_delivery_uses_browser_identity_and_no_credentials(self):
        Receiver.seen = []
        server = ThreadingHTTPServer(("127.0.0.1", 0), Receiver)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            self.service.save(dict(url=f"http://127.0.0.1:{server.server_port}/private", enabled=True))
            result = self.service.send(dict(event="test", title="Fixture", status="test"))
            self.assertTrue(result["ok"])
            _, headers, body = Receiver.seen[0]
            self.assertIn("Mozilla/", headers["User-Agent"])
            self.assertNotIn("Cookie", headers)
            self.assertNotIn("Authorization", headers)
            self.assertEqual(body["source"], "Kiroshi")
        finally:
            server.shutdown()
            server.server_close()

    def test_dispatch_filters_events_and_deduplicates_without_blocking(self):
        self.service.save(dict(url="https://notify.example.test/private", events=["workflow_completed"], enabled=True))
        event = dict(id="fixture", event="workflow_completed", status="completed")
        with patch.object(self.service, "send") as send:
            self.service.enqueue({**event, "event": "job_completed"})
            self.service.enqueue(event)
            self.service.enqueue(event)
            deadline = time.monotonic() + 1
            while not send.called and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertEqual(send.call_count, 1)


if __name__ == "__main__":
    unittest.main()
