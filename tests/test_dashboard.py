import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from dashboard.server import App
from dashboard.tools import allowed, rules, target_url


class ScopeTests(unittest.TestCase):
    def setUp(self):
        self.engagement = dict(scope=rules("example.com *.example.com"), excluded=rules("admin.example.com *.private.example.com"))

    def test_exact_and_wildcard_boundaries(self):
        for target in ("example.com", "a.example.com", "deep.a.example.com"):
            self.assertTrue(allowed(target, self.engagement))
        for target in ("evilexample.com", "example.com.evil.test", "admin.example.com", "a.private.example.com"):
            self.assertFalse(allowed(target, self.engagement))
        self.assertFalse(allowed("example.com", dict(scope=["*.example.com"], excluded=[])))

    def test_unsafe_urls_rejected(self):
        for value in ("https://example.com@evil.test", "file:///etc/passwd", "https://example.com\\@evil.test", "https://example.com\nHost: evil.test", "https://example.com:99999", "https://evil.test", "https://user:secret@example.com"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                target_url(value, self.engagement)
        self.assertEqual(target_url("https://EXAMPLE.com/path", self.engagement)[1], "example.com")

    def test_invalid_scope(self):
        for value in ("https://example.com", "example.com/path", "example.com:443", "../", "*.127.0.0.1"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                rules(value)


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.app = App(self.directory.name)
        self.e = self.app.save_engagement(dict(name="Local lab", scope="127.0.0.1", excluded="", policy="Local fixture only", authorized=True, duration=10))

    def tearDown(self):
        self.app.shutdown()
        self.app.db.close()
        self.directory.cleanup()

    def test_original_scaffold_and_shared_state(self):
        workspace = self.app.workspace(self.e)
        self.assertTrue((workspace / "upstream/brief/AGENT.md").exists())
        self.assertIn("@AGENTS.md", (workspace / "CLAUDE.md").read_text())
        (workspace / "handoff.md").write_text("Retain this state")
        self.app.save_engagement({**self.e, "rate": 2})
        self.assertEqual((workspace / "handoff.md").read_text(), "Retain this state")

    def test_auth_binding_and_metadata(self):
        session = self.app.save_auth(dict(engagement_id=self.e["id"], label="Account A", origin="http://127.0.0.1:9999", cookie="sid=private-value", headers="Authorization: Bearer private-token"))
        self.assertNotIn("private-value", json.dumps(self.app.all("auth")))
        file = Path(self.directory.name) / "secrets" / f"{session['id']}.json"
        self.assertEqual(file.stat().st_mode & 0o777, 0o600)
        payload = dict(engagement_id=self.e["id"], tool="httpx", target="http://127.0.0.1:9999", auth_id=session["id"])
        self.assertEqual(self.app.selected_auth(payload, self.e)["id"], session["id"])
        for target in ("https://127.0.0.1:9999", "http://127.0.0.1:8888"):
            with self.assertRaises(ValueError):
                self.app.selected_auth({**payload, "target": target}, self.e)
        with self.assertRaises(ValueError):
            self.app.selected_auth({**payload, "tool": "subfinder"}, self.e)
        for headers in ("Host: evil.test", "Content-Length: 4", "Broken header"):
            with self.assertRaises(ValueError):
                self.app.save_auth(dict(engagement_id=self.e["id"], label="bad", origin="http://127.0.0.1", headers=headers))

    def test_job_snapshot_redaction_cache_and_failure(self):
        executable = Path(self.directory.name) / "fake-httpx"
        executable.write_text("#!/usr/bin/env python3\nimport json,sys\nfrom pathlib import Path\nargs=sys.argv\nconfig=json.loads(Path(args[args.index('-config')+1]).read_text())\nprint(config['header'][0],flush=True)\nprint(json.dumps({'url':'http://127.0.0.1:9999/asset'}),flush=True)\n")
        executable.chmod(0o700)
        self.app.put("settings", dict(id="local", paths={"httpx": str(executable)}))
        session = self.app.save_auth(dict(engagement_id=self.e["id"], label="Account A", origin="http://127.0.0.1:9999", cookie="sid=secret"))
        payload = dict(engagement_id=self.e["id"], tool="httpx", target="http://127.0.0.1:9999", auth_id=session["id"])
        job = self.app.enqueue(payload)
        self.assertNotIn("sid=secret", json.dumps(job))
        result = self.wait_job(job["id"])
        self.assertEqual(result["status"], "completed")
        output = self.app.logpath(job).read_text()
        self.assertIn("[REDACTED]", output)
        self.assertNotIn("sid=secret", output)
        self.assertFalse((self.app.logpath(job).parent / "session.json").exists())
        self.assertFalse((self.app.logpath(job).parent / "headers.json").exists())
        self.assertEqual(len(self.app.all("asset")), 1)
        # Changing identities retains and deduplicates cached assets.
        self.app.cache_asset({**job, "id": "anonymous-run", "identity": "Anonymous"}, "http://127.0.0.1:9999/asset", {})
        self.assertEqual(len(self.app.all("asset")), 1)
        self.assertEqual(len(self.app.all("asset")[0]["job_ids"]), 2)
        executable.write_text("#!/bin/sh\nexit 7\n")
        failed = self.wait_job(self.app.enqueue({**payload, "auth_id": ""})["id"])
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["returncode"], 7)

    def test_cancel_and_scope_edit_gate(self):
        executable = Path(self.directory.name) / "sleep-tool"
        executable.write_text("#!/usr/bin/env python3\nimport time\nprint('started',flush=True)\ntime.sleep(30)\n")
        executable.chmod(0o700)
        self.app.put("settings", dict(id="local", paths={"httpx": str(executable)}))
        job = self.app.enqueue(dict(engagement_id=self.e["id"], tool="httpx", target="http://127.0.0.1"))
        with self.assertRaises(ValueError):
            self.app.save_engagement(self.e)
        deadline = time.monotonic() + 3
        while self.app.get("job", job["id"])["status"] == "queued" and time.monotonic() < deadline:
            time.sleep(.02)
        self.app.cancel(job["id"])
        self.assertEqual(self.wait_job(job["id"])["status"], "cancelled")

    def test_timeout_and_log_limit_terminate_job(self):
        executable = Path(self.directory.name) / "bounded-tool"
        executable.write_text("#!/usr/bin/env python3\nimport time\ntime.sleep(30)\n")
        executable.chmod(0o700)
        self.app.put("settings", dict(id="local", paths={"httpx": str(executable)}))
        with self.app.lock:
            job = self.app.enqueue(dict(engagement_id=self.e["id"], tool="httpx", target="http://127.0.0.1"))
            job["duration"] = .15
            self.app.put("job", job)
        self.assertEqual(self.wait_job(job["id"])["status"], "timed_out")
        executable.write_text("#!/usr/bin/env python3\nprint('x'*100000,flush=True)\n")
        with patch("dashboard.server.MAX_LOG", 128):
            job = self.app.enqueue(dict(engagement_id=self.e["id"], tool="httpx", target="http://127.0.0.1"))
            self.assertEqual(self.wait_job(job["id"])["status"], "output_limit")
        self.assertLessEqual(self.app.logpath(job).stat().st_size, 128)

    def test_restart_retains_cache_and_cleans_private_files(self):
        job = dict(id="interrupted-job", tool="httpx", status="running", engagement_id=self.e["id"], identity="Anonymous")
        self.app.put("job", job)
        self.app.cache_asset(job, "http://127.0.0.1/", {})
        folder = self.app.logpath(job).parent
        folder.mkdir(parents=True)
        (folder / "session.json").write_text('{"cookie":"old-secret"}')
        self.app.shutdown()
        self.app.db.close()
        self.app = App(self.directory.name)
        self.assertEqual(self.app.get("job", job["id"])["status"], "interrupted")
        self.assertFalse((folder / "session.json").exists())
        self.assertEqual(len(self.app.all("asset")), 1)

    def wait_job(self, key):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            with self.app.lock:
                job = self.app.get("job", key)
            if job["status"] not in ("queued", "running", "cancelling"):
                return job
            time.sleep(.03)
        self.fail("Job failed to finish")


if __name__ == "__main__":
    unittest.main()
