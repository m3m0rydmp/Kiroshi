from datetime import datetime, timedelta, timezone
import json
import tempfile
import unittest
from unittest.mock import patch

from dashboard.readiness import FIELDS, content_hash, evaluate, normalize_review, related
from dashboard.references import Collector, normalize, report_id
from dashboard.references import read_json
from dashboard.http_identity import browser_user_agent
from dashboard.server import App


def complete_review():
    return {**{key: f"Local fixture evidence for {key}: recorded baseline and independent reproduction." for key in FIELDS},
            "eligibility": "eligible", "impact_assessment": "demonstrated", "false_positive_assessment": "ruled_out",
            "reproduction_attempts": 2, "policy_checked_at": datetime.now(timezone.utc).date().isoformat(),
            "reviewer": "Local reviewer", "attested": True, "reference_ids": []}


def public_report(identifier="123"):
    return dict(id=int(identifier), title="Cross-tenant project access control bypass", public=True,
                disclosed_at="2020-01-02T00:00:00Z", substate="resolved", bounty_amount="500.00",
                team={"handle": "fixture", "default_currency": "usd"}, weakness={"name": "Improper Access Control"},
                vulnerability_information="Public fixture description. " * 150)


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.app = App(self.temporary.name)
        self.e = self.app.save_engagement(dict(name="Review fixture", scope="example.test", policy="https://example.test/policy", authorized=True))
        self.payload = dict(engagement_id=self.e["id"], title="Cross-tenant project access control bypass", target="https://example.test/project/owned", severity="medium", notes="Local test fixture notes", status="unverified")

    def tearDown(self):
        self.app.shutdown()
        self.app.db.close()
        self.temporary.cleanup()

    def test_draft_has_gaps_and_confirmed_cannot_bypass_api_gate(self):
        draft = self.app.save_finding(self.payload)
        self.assertEqual(draft["readiness"]["disposition"], "needs_evidence")
        for status in ("confirmed", "reported"):
            with self.assertRaisesRegex(ValueError, "Evidence review required"):
                self.app.save_finding({**self.payload, "status": status})
        self.assertEqual(len(self.app.all("finding")), 1)

    def test_complete_review_and_content_change_invalidation(self):
        ready = self.app.save_finding({**self.payload, "review": complete_review(), "status": "confirmed"})
        self.assertTrue(ready["readiness"]["ready"])
        with self.assertRaisesRegex(ValueError, "Evidence review required"):
            self.app.save_finding({**self.payload, "id": ready["id"], "notes": "Changed evidence", "status": "confirmed"})
        changed = self.app.save_finding({**self.payload, "id": ready["id"], "notes": "Changed evidence"})
        self.assertFalse(changed["readiness"]["ready"])
        self.assertIn("Named reviewer attests to this evidence", changed["readiness"]["gaps"])

    def test_policy_changes_and_expiry_invalidate_readiness(self):
        finding = self.app.save_finding({**self.payload, "review": complete_review()})
        changed_policy = {**self.e, "notes": "New exclusion or program constraints"}
        self.assertFalse(evaluate(finding, changed_policy)["ready"])
        future = datetime.now(timezone.utc).date() + timedelta(days=31)
        self.assertFalse(evaluate(finding, self.e, today=future)["ready"])

    def test_informational_expected_and_excluded_dispositions(self):
        for field, value, expected in (
            ("impact_assessment", "informational", "likely_informational"),
            ("impact_assessment", "expected_behavior", "likely_excluded_or_expected"),
            ("eligibility", "excluded", "likely_excluded_or_expected"),
            ("false_positive_assessment", "identified", "likely_excluded_or_expected"),
        ):
            with self.subTest(field=field, value=value):
                finding = self.app.save_finding({**self.payload, "review": {**complete_review(), field: value}})
                self.assertEqual(finding["readiness"]["disposition"], expected)
                self.assertFalse(finding["readiness"]["ready"])

    def test_public_reward_never_increases_readiness(self):
        reference = normalize(public_report(), "123")
        self.app.put("reference", reference)
        draft = self.app.save_finding({**self.payload, "review": {"reference_ids": [reference["id"]]}})
        self.assertFalse(draft["readiness"]["ready"])
        self.assertTrue(draft["related_references"][0]["rewarded"])
        before = draft["readiness"]["completed"]
        reference["bounty_amount"] = "1000000"
        self.app.put("reference", reference)
        self.assertEqual(self.app.finding_view(draft)["readiness"]["completed"], before)

    def test_preview_does_not_save_and_exports_shared_agent_guidance(self):
        preview = self.app.save_finding({**self.payload, "review": complete_review()}, preview=True)
        self.assertTrue(preview["readiness"]["ready"])
        self.assertEqual(self.app.all("finding"), [])
        workspace = self.app.workspace(self.e)
        self.assertIn("Read QUALITY.md", (workspace / "AGENTS.md").read_text())
        self.assertIn("false positives", (workspace / "QUALITY.md").read_text())
        self.assertTrue((workspace / "public-references.json").exists())

    def test_cached_import_and_partial_failures(self):
        reference = normalize(public_report(), "123")
        self.app.put("reference", reference)
        with patch.object(self.app.collector, "fetch") as fetch:
            result = self.app.import_references({"urls": ["123"]})
            fetch.assert_not_called()
            self.assertEqual(result["cached"], ["h1-123"])
            fetch.side_effect = [normalize(public_report("456"), "456"), ValueError("Not public")]
            result = self.app.import_references({"urls": ["456", "789"]})
            self.assertEqual(result["imported"], ["h1-456"])
            self.assertEqual(result["errors"][0]["report_id"], "789")
        with self.assertRaises(ValueError):
            self.app.import_references({"urls": [str(i) for i in range(1, 7)]})
        exported = json.loads((self.app.workspace(self.e) / "public-references.json").read_text())
        self.assertEqual(len(exported["references"]), 2)

    def test_invalid_review_rejected(self):
        for value in ({"eligibility": "definitely-paid"}, {"reproduction_attempts": -1}, {"reference_ids": "123"}):
            with self.assertRaises(ValueError):
                normalize_review(value)


class PublicReferenceTests(unittest.TestCase):
    def test_public_fetch_uses_browser_identity_without_session_credentials(self):
        with patch("dashboard.references.build_opener") as factory:
            response = factory.return_value.open.return_value.__enter__.return_value
            response.read.return_value = b'{"id":123}'
            read_json("https://hackerone.com/reports/123.json")
            request = factory.return_value.open.call_args.args[0]
            self.assertEqual(request.get_header("User-agent"), browser_user_agent())
            self.assertIsNone(request.get_header("Cookie"))
            self.assertIsNone(request.get_header("Authorization"))

    def test_reference_urls_cannot_address_local_network_or_arbitrary_hosts(self):
        self.assertEqual(report_id("https://hackerone.com/reports/123"), "123")
        for url in ("http://hackerone.com/reports/123", "https://hackerone.com.evil.test/reports/123", "https://user@hackerone.com/reports/123", "https://hackerone.com:443/reports/123", "http://127.0.0.1/reports/123", "https://hackerone.com/reports/123?redirect=http://localhost", "https://hackerone.com/login"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                report_id(url)

    def test_only_explicitly_public_and_disclosed_imported(self):
        for changes in ({"public": False}, {"public": "true"}, {"disclosed_at": None}, {"id": 456}):
            with self.assertRaises(ValueError):
                normalize({**public_report(), **changes}, "123")
        reference = normalize(public_report(), "123")
        self.assertTrue(reference["rewarded"])
        self.assertLessEqual(len(reference["excerpt"].split()), 100)
        self.assertNotIn("vulnerability_information", reference)

    def test_unknown_reward_does_not_mean_zero(self):
        self.assertIsNone(normalize({**public_report(), "bounty_amount": None}, "123")["rewarded"])
        self.assertFalse(normalize({**public_report(), "bounty_amount": "0"}, "123")["rewarded"])
        self.assertIsNone(normalize({**public_report(), "bounty_amount": "Infinity"}, "123")["rewarded"])

    def test_discovery_filters_private_rows_and_does_not_return_credentials(self):
        collector = Collector()
        public = {"id": 123, "attributes": {"title": "Public", "disclosed": True, "disclosed_at": "2020-01-01"}}
        private = {"id": 456, "attributes": {"title": "Private", "disclosed": False}}
        with patch.dict("os.environ", {"KIROSHI_H1_API_USERNAME": "local-test", "KIROSHI_H1_API_TOKEN": "secret-test"}), patch("dashboard.references.read_json", return_value={"data": [public, private]}) as fetch:
            result = collector.discover("team:fixture")
            self.assertEqual(len(result["results"]), 1)
            self.assertNotIn("secret-test", json.dumps(result))
            self.assertTrue(fetch.call_args.args[0].startswith("https://api.hackerone.com/v1/hackers/hacktivity?"))
            self.assertIn("disclosed%3Atrue", fetch.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
