"""Workflow regressions using temporary workspaces and fake executables only."""
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from dashboard.server import App
from dashboard.tools import rules, target_url
from dashboard.traffic import Feedback, normalize


class BusinessLogicTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.app = App(self.directory.name)
        self.e = self.app.save_engagement(dict(name="Workflow fixture", scope="example.test", authorized=True))

    def tearDown(self):
        self.app.shutdown()
        self.app.db.close()
        self.directory.cleanup()

    def session(self, **changes):
        return self.app.save_auth(dict(engagement_id=self.e["id"], origin="https://example.test", label="A", cookie="sid=fixture", **changes))

    def test_default_ports_bind_to_the_same_origin(self):
        auth = self.session()
        payload = dict(engagement_id=self.e["id"], tool="httpx", auth_id=auth["id"], target="https://EXAMPLE.test:443/")
        self.assertEqual(self.app.selected_auth(payload, self.e)["id"], auth["id"])
        for target in ("http://example.test", "https://example.test:444"):
            with self.assertRaises(ValueError):
                self.app.selected_auth({**payload, "target": target}, self.e)

    def test_session_origins_cannot_silently_drop_boundaries(self):
        for origin in ("https://example.test/private", "https://example.test?token=fixture", "https://example.test/#fragment"):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                self.app.save_auth(dict(engagement_id=self.e["id"], origin=origin, label="A", cookie="sid=fixture"))
        self.assertEqual(self.app.all("auth"), [])

    def test_duplicate_identity_is_server_owned(self):
        payload = dict(engagement_id=self.e["id"], tool="httpx", target="https://example.test")
        preview = dict(argv=["/fixture"], auth_id=None, traffic={}, duration=10)
        with self.app.lock, patch.object(self.app, "preview", return_value=preview):
            self.app.enqueue(payload)
            for auth_version in ("forged-revision", 123, ["arbitrary"]):
                with self.assertRaisesRegex(ValueError, "pending run"):
                    self.app.enqueue({**payload, "auth_version": auth_version})
            for job in self.app.all("job"):
                self.app.cancel(job["id"])

    def test_host_adapters_deduplicate_the_effective_target(self):
        for tool in ("dnsx", "subfinder", "tlsx"):
            payload = dict(engagement_id=self.e["id"], tool=tool, target="https://example.test/a")
            self.assertEqual(self.app.run_key(payload), self.app.run_key({**payload, "target": "http://example.test/b"}))
        payload = dict(engagement_id=self.e["id"], tool="tlsx", target="https://example.test:444")
        self.assertNotEqual(self.app.run_key(payload), self.app.run_key({**payload, "target": "https://example.test"}))

    def test_session_replacement_creates_a_new_revision(self):
        auth = self.session()
        payload = dict(engagement_id=self.e["id"], tool="httpx", target="https://example.test", auth_id=auth["id"])
        previous = self.app.run_key(payload)
        replacement = self.app.save_auth(dict(id=auth["id"], engagement_id=self.e["id"], origin=auth["origin"], label="A", cookie="sid=changed"))
        self.assertNotEqual(auth["revision"], replacement["revision"])
        self.assertNotEqual(previous, self.app.run_key(payload))

    def test_scanner_findings_stay_scoped_and_preserve_review(self):
        job = dict(id="fixture", engagement_id=self.e["id"], tool="nuclei", target="https://example.test", auth_id=None)
        log = self.app.logpath(job)
        log.parent.mkdir(parents=True)
        row = {"template-id": "fixture-template", "matched-at": "https://example.test", "info": {"name": "Observation", "severity": "low"}}
        outside = {**row, "matched-at": "https://outside.test"}
        malformed = {**row, "matched-at": ["invalid"]}
        log.write_text("\n".join(json.dumps(r) for r in (outside, malformed, row, row)))
        self.app.extract(job)
        finding, = self.app.all("finding")
        finding.update(status="dismissed", notes="Reviewed and expected", review={"attested": False})
        self.app.save_finding(finding)
        self.assertEqual(self.app.get("finding", finding["id"])["observed_job_ids"], [job["id"]])
        self.app.extract(job)
        retained, = self.app.all("finding")
        self.assertEqual(retained["status"], "dismissed")
        self.assertEqual(retained["notes"], "Reviewed and expected")
        self.assertEqual(retained["observed_job_ids"], [job["id"]])

    def test_malformed_info_does_not_break_scanner_processing(self):
        job = dict(id="fixture", engagement_id=self.e["id"], tool="nuclei", target="https://example.test")
        log = self.app.logpath(job)
        log.parent.mkdir(parents=True)
        log.write_text(json.dumps({"template-id": "fixture-template", "info": ["invalid"]}))
        self.app.extract(job)
        finding, = self.app.all("finding")
        self.assertEqual(finding["severity"], "info")

    def test_processing_failure_does_not_rewrite_process_outcome(self):
        binary = Path(self.directory.name) / "fake-httpx"
        binary.write_text("#!/usr/bin/env python3\nprint('{}')\n")
        binary.chmod(0o700)
        self.app.put("settings", dict(id="local", paths={"httpx": str(binary)}))
        with patch.object(self.app, "extract", side_effect=ValueError("fixture parser failure")):
            job = self.app.enqueue(dict(engagement_id=self.e["id"], tool="httpx", target="https://example.test"))
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                result = self.app.get("job", job["id"])
                if result.get("processing_error"):
                    break
                time.sleep(.02)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["returncode"], 0)
        self.assertIn("processing_error", result)

    def test_scope_edits_refresh_generated_checklist(self):
        workspace = self.app.workspace(self.e)
        (workspace / "scope-hosts.md").write_text("# Scope hosts\n\n- [x] example.test\n- [x] removed.test\n")
        (workspace / "handoff.md").write_text("Retain these user notes")
        self.app.save_engagement({**self.e, "scope": ["example.test", "new.test"]})
        checklist = (workspace / "scope-hosts.md").read_text()
        self.assertIn("- [x] example.test", checklist)
        self.assertIn("- [ ] new.test", checklist)
        self.assertNotIn("removed.test", checklist)
        self.assertEqual((workspace / "handoff.md").read_text(), "Retain these user notes")

    def test_policy_edits_refresh_exported_review_readiness(self):
        from tests.test_readiness import complete_review
        self.e = self.app.save_engagement({**self.e, "policy": "https://example.test/policy"})
        finding = self.app.save_finding(dict(engagement_id=self.e["id"], title="Fixture evidence", target="https://example.test", severity="low", status="confirmed", review=complete_review()))
        exported = self.app.workspace(self.e) / "findings" / (finding["id"] + ".review.json")
        self.assertTrue(json.loads(exported.read_text())["readiness"]["ready"])
        self.app.save_engagement({**self.e, "notes": "Changed policy constraints"})
        snapshot = json.loads(exported.read_text())
        self.assertFalse(snapshot["readiness"]["ready"])
        self.assertEqual(snapshot["status"], "confirmed")  # Preserve historical workflow status.
        self.assertIn("evaluated_at", snapshot)

    def test_bare_ipv6_and_status_aliases(self):
        e = dict(scope=rules("2001:db8::1"), excluded=[])
        self.assertEqual(target_url("2001:db8::1", e)[0], "https://[2001:db8::1]")
        for row in ({"status-code": 429}, {"status": "429"}, {"response": {"status_code": 429}}):
            event = Feedback(normalize({})).observe(json.dumps(row))
            self.assertEqual(event["status_code"], 429)


if __name__ == "__main__":
    unittest.main()
