from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import json
from pathlib import Path
import tempfile
import time
import unittest

from dashboard.server import App
from dashboard.tools import command
from dashboard.traffic import Feedback, effective, normalize, retry_after


class TrafficRulesTests(unittest.TestCase):
    def setUp(self):
        self.e = dict(scope=["example.test"], excluded=[], rate=5, duration=30, traffic={})
        self.tools = [dict(name=name, installed=True, adapter=True, path="/fixture/" + name)
                      for name in ("httpx", "ffuf", "feroxbuster", "katana")]

    def test_rate_cannot_exceed_engagement_ceiling(self):
        with self.assertRaises(ValueError):
            effective(self.e, dict(tool="httpx", rate=6))
        gentle = effective(self.e, dict(tool="ffuf", traffic_profile="gentle", delay_ms=500, jitter_ms=500))
        self.assertEqual((gentle["rate"], gentle["concurrency"], gentle["jitter_ms"]), (1, 1, 0))

    def test_flags_are_native_and_unsupported_controls_rejected(self):
        args = command(self.e, dict(tool="ffuf", target="https://example.test", rate=2, delay_ms=200, jitter_ms=300), self.tools)
        self.assertEqual(args[args.index("-rate") + 1], "2")
        self.assertEqual(args[args.index("-p") + 1], "0.200-0.500")
        args = command(self.e, dict(tool="katana", target="https://example.test", delay_ms=500), self.tools)
        self.assertEqual(args[args.index("-rd") + 1], "1")
        for tool, extra in (("feroxbuster", {"delay_ms": 100}), ("httpx", {"jitter_ms": 100})):
            with self.assertRaises(ValueError):
                command(self.e, dict(tool=tool, target="https://example.test", **extra), self.tools)

    def test_retry_after_numeric_date_and_manual_hold(self):
        clock = datetime(2026, 10, 15, tzinfo=timezone.utc)
        self.assertEqual(retry_after("45", clock), (45, False))
        self.assertEqual(retry_after(format_datetime(clock + timedelta(seconds=90)), clock), (90, False))
        self.assertEqual(retry_after("90000", clock), (0, True))
        self.assertEqual(retry_after("invalid", clock), (0, False))

    def test_status_observation_threshold_and_403_opt_in(self):
        feedback = Feedback(normalize({"block_threshold": 2}))
        self.assertIsNone(feedback.observe('{"status_code":403}\n{"status_code":429}\n'))
        self.assertIsNone(feedback.observe('{"status_code":200}\n{"status_code":429}\n'))
        event = feedback.observe('{"response":{"status_code":429,"headers":{"Retry-After":"60"}}}\n')
        self.assertEqual(event["delay"], 60)
        self.assertEqual(event["status_code"], 429)
        httpx = Feedback(normalize({"cooldown": 1}))
        self.assertEqual(httpx.observe('{"status_code":429,"header":{"retry_after":"90"}}')["delay"], 90)
        observe = Feedback(normalize({"stop_on_block": False}))
        self.assertIsNone(observe.observe('{"status":503}\n'))
        self.assertEqual(len(observe.events), 1)


class TrafficQueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = App(self.temp.name)
        self.e = self.app.save_engagement(dict(name="Traffic fixture", scope="127.0.0.1 localhost", authorized=True,
                                              traffic={"cooldown": 1}, duration=10))
        binary = Path(self.temp.name) / "mock-httpx"
        binary.write_text("#!/usr/bin/env python3\nimport json,sys,time\ntarget=sys.argv[sys.argv.index('-u')+1]\nif 'throttle' in target:\n print(json.dumps({'status_code':429,'response':{'headers':{'Retry-After':'0'}}}),flush=True)\n time.sleep(30)\nelse:\n print(json.dumps({'status_code':200,'url':target}),flush=True)\n")
        binary.chmod(0o700)
        self.app.put("settings", dict(id="local", paths={"httpx": str(binary)}))

    def tearDown(self):
        self.app.shutdown()
        self.app.db.close()
        self.temp.cleanup()

    def enqueue(self, target):
        return self.app.enqueue(dict(engagement_id=self.e["id"], tool="httpx", target=target))

    def done(self, job):
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            record = self.app.get("job", job["id"])
            if record["status"] not in ("queued", "running", "cancelling"):
                return record
            time.sleep(.02)
        self.fail("Job did not finish")

    def test_block_stops_job_and_other_origin_can_continue(self):
        job = self.done(self.enqueue("http://127.0.0.1:9999/throttle"))
        self.assertEqual(job["status"], "rate_limited")
        self.assertEqual(job["traffic_events"][0]["status_code"], 429)
        gate = self.app.traffic_gate(job)
        same = self.enqueue("http://127.0.0.1:9999/allowed")
        other = self.enqueue("http://localhost:9999/allowed")
        self.assertEqual(self.done(other)["status"], "completed")
        completed = self.done(same)
        self.assertEqual(completed["status"], "completed")
        # Persisted timestamps are second-granular; allow less than one second rounding.
        self.assertGreaterEqual(datetime.fromisoformat(completed["started"]).timestamp(), gate["until"] - 1)
        self.assertEqual(self.app.get("job", job["id"])["status"], "rate_limited")

    def test_manual_hold_requires_reason_and_clearance(self):
        seed = dict(id="fixture", engagement_id=self.e["id"], target="http://127.0.0.1:9999", tool="httpx")
        gate = self.app.set_traffic_gate(seed, dict(delay=1, manual_hold=True, status_code=429, reason="Fixture"))
        queued = self.enqueue("http://127.0.0.1:9999/allowed")
        other = self.enqueue("http://localhost:9999/allowed")
        self.assertEqual(self.done(other)["status"], "completed")
        self.assertEqual(self.app.get("job", queued["id"])["status"], "queued")
        with self.assertRaises(ValueError):
            self.app.clear_traffic_gate(dict(id=gate["id"], reason=""))
        self.app.clear_traffic_gate(dict(id=gate["id"], reason="Approved local fixture retest"))
        self.assertEqual(self.done(queued)["status"], "completed")


if __name__ == "__main__":
    unittest.main()
