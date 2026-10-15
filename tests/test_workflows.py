import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from dashboard.server import App
from dashboard.tools import command, target_url


FAKE = '''#!/usr/bin/env python3
import json,sys
from pathlib import Path
from urllib.parse import urlsplit
tool=Path(sys.argv[0]).name
args=sys.argv
if '-h' in args or '--help' in args:
 print('-max-time -rate-limit -url-scope -rcode -resp-only -status-code -no-fallback-scheme -tls-version -scan-mode -crawl-scope -disable-redirects -maxtime -noninteractive -no-interactsh')
 sys.exit(0)
key='-d' if tool in ('subfinder','urlfinder') else '-l' if tool=='dnsx' else '-u'
target=args[args.index(key)+1]
if tool=='subfinder': print('new.example.test')
elif tool=='urlfinder':
 print(json.dumps({'url':'https://'+target+'/archived'}))
 print(json.dumps({'url':'https://outside.test/never-probe'}))
elif tool in ('dnsx','tlsx'): print(json.dumps({'host':target}))
elif tool=='katana': print(json.dumps({'request':{'endpoint':target.rstrip('/')+'/crawled'},'response':{'status_code':200}}))
elif tool=='ffuf': print(json.dumps({'url':target.replace('FUZZ','fuzzed'),'status':200}))
elif tool=='nuclei': print(json.dumps({'template-id':'fixture','matched-at':target,'info':{'severity':'info','name':'Fixture inventory'}}))
else: print(json.dumps({'url':target,'status_code':200}),flush=True)
'''


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.app = App(self.directory.name)
        self.e = self.app.save_engagement(dict(name="Sequential fixture", scope="example.test *.example.test", authorized=True, duration=10))
        self.tools = []
        for name in ("subfinder", "dnsx", "httpx", "tlsx", "urlfinder", "katana", "ffuf", "nuclei"):
            path = Path(self.directory.name) / name
            path.write_text(FAKE)
            path.chmod(0o700)
            self.tools.append(dict(name=name, path=str(path), installed=True, adapter=True, runnable=True))
        self.mock = patch.object(self.app, "tools", return_value=self.tools)
        self.mock.start()
        self.payload = dict(engagement_id=self.e["id"], max_jobs=150, max_targets=50)

    def tearDown(self):
        self.app.shutdown()
        self.app.db.close()
        self.mock.stop()
        self.directory.cleanup()

    def start(self, **changes):
        payload = {**self.payload, **changes}
        plan = self.app.workflow_plan(payload)
        return self.app.start_workflow({**payload, "plan_token": plan["plan_token"]})

    def done(self, workflow):
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            result = self.app.get("workflow", workflow["id"])
            if result["status"] not in ("queued", "running"):
                return result
            time.sleep(.03)
        self.fail("Workflow did not finish")

    def test_sequential_pipeline_reprobes_each_new_discovery(self):
        workflow = self.done(self.start())
        self.assertEqual(workflow["status"], "completed", workflow.get("error"))
        jobs = [self.app.get("job", key) for key in workflow["job_ids"]]
        self.assertEqual([j["workflow_stage"] for j in jobs], sorted(j["workflow_stage"] for j in jobs))
        for stage, suffix in ((6, "/archived"), (8, "/crawled"), (10, "/fuzzed")):
            probes = [j for j in jobs if j["tool"] == "httpx" and j["workflow_stage"] == stage]
            self.assertTrue(any(suffix in j["target"] for j in probes), (stage, probes))
        self.assertFalse(any("outside.test" in j["target"] for j in jobs))
        view = self.app.workflow_view(workflow)
        self.assertNotIn("seen", view)
        self.assertTrue(all("targets" not in stage for stage in view["stages"]))
        self.assertEqual(len({j["run_key"] for j in jobs}), len(jobs))
        self.assertTrue(all(j["diagnostics"] for j in jobs))
        self.assertTrue(all(j["status"] == "completed" for j in jobs))

    def test_plan_must_be_previewed_and_active_workflow_is_unique(self):
        with self.assertRaisesRegex(ValueError, "Preview"):
            self.app.start_workflow(self.payload)
        with self.app.lock:
            workflow = self.start()
            with self.assertRaisesRegex(ValueError, "active workflow"):
                self.start()
            with self.assertRaisesRegex(ValueError, "active workflow"):
                self.app.save_engagement(self.e)
            self.app.cancel_workflow(workflow["id"])
        self.assertEqual(self.app.all("job"), [])

    def test_scope_change_invalidates_a_preview(self):
        plan = self.app.workflow_plan(self.payload)
        self.app.save_engagement({**self.e, "notes": "Changed constraints"})
        with self.assertRaisesRegex(ValueError, "Preview"):
            self.app.start_workflow({**self.payload, "plan_token": plan["plan_token"]})

    def test_job_limit_reports_partial_coverage(self):
        workflow = self.done(self.start(max_jobs=2))
        self.assertEqual(workflow["status"], "completed_limited")
        self.assertTrue(workflow["limited"])
        self.assertEqual(len(workflow["job_ids"]), 2)

    def test_missing_tools_are_reported_as_skipped(self):
        self.tools[:] = [t for t in self.tools if t["name"] == "httpx"]
        workflow = self.done(self.start())
        self.assertEqual(workflow["status"], "completed_limited")
        self.assertEqual(workflow["stages"][0]["status"], "skipped")
        self.assertEqual({self.app.get("job", key)["tool"] for key in workflow["job_ids"]}, {"httpx"})

    def test_restart_interrupts_workflows_without_replaying_them(self):
        with self.app.lock:
            workflow = self.start()
            self.app.stop.set()
        self.app.shutdown()
        self.app.db.close()
        self.mock.stop()
        self.app = App(self.directory.name)
        self.assertEqual(self.app.get("workflow", workflow["id"])["status"], "interrupted")
        self.assertEqual(self.app.all("job"), [])

    def test_live_metrics_and_diagnostics_do_not_change_duplicate_identity(self):
        payload = dict(engagement_id=self.e["id"], tool="httpx", target="https://example.test")
        self.assertEqual(self.app.run_key(payload), self.app.run_key({**payload, "diagnostics": True}))
        args = command(self.e, {**payload, "diagnostics": True}, self.tools)
        self.assertNotIn("-silent", args)
        self.assertIn("-stats", args)
        job = dict(id="metrics", status="running", started_epoch=time.time()-4)
        log = self.app.logpath(job)
        log.parent.mkdir(parents=True)
        log.write_text("live fixture\n")
        os.utime(log, (time.time()-2, time.time()-2))
        view = self.app.job_view(job)
        self.assertGreaterEqual(view["elapsed_seconds"], 4)
        self.assertEqual(view["log_bytes"], len("live fixture\n"))
        self.assertGreaterEqual(view["quiet_seconds"], 2)
        self.assertNotIn("elapsed_seconds", job)

    def test_session_change_stops_workflow_before_any_probe(self):
        auth = self.app.save_auth(dict(engagement_id=self.e["id"], origin="https://example.test", label="Fixture", cookie="sid=first"))
        with self.app.lock:
            workflow = self.start(auth_id=auth["id"])
            self.app.save_auth(dict(id=auth["id"], engagement_id=self.e["id"], origin="https://example.test", label="Fixture", cookie="sid=second"))
        result = self.done(workflow)
        self.assertEqual(result["status"], "failed")
        self.assertIn("session changed", result["error"])
        self.assertEqual(result["job_ids"], [])

    def test_completion_notification_is_local_and_contains_only_a_summary(self):
        from http.server import ThreadingHTTPServer
        import threading
        from tests.test_notifications import Receiver
        Receiver.seen = []
        receiver = ThreadingHTTPServer(("127.0.0.1", 0), Receiver)
        threading.Thread(target=receiver.serve_forever, daemon=True).start()
        try:
            self.app.notifications.save(dict(url=f"http://127.0.0.1:{receiver.server_port}/private", enabled=True))
            workflow = self.done(self.start(max_jobs=2))
            deadline = time.monotonic() + 2
            while not Receiver.seen and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertEqual(len(Receiver.seen), 1)
            body = Receiver.seen[0][2]
            self.assertEqual(body["event"], "workflow_completed")
            self.assertEqual(body["fields"]["Status"], "completed_limited")
            self.assertIn("limited", body["summary"])
            self.assertNotIn("argv", body)
            self.assertNotIn("output", body)
        finally:
            self.app.notifications.save(dict(remove=True))
            receiver.shutdown()
            receiver.server_close()

    def test_cancelling_the_current_job_cancels_its_workflow(self):
        with self.app.lock:
            workflow = self.start()
            self.app.advance_workflow(workflow)
            current = self.app.get("workflow", workflow["id"])
            self.app.cancel(current["active_job"])
            self.app.advance_workflow(current)
        result = self.app.get("workflow", workflow["id"])
        self.assertEqual(result["status"], "cancelled")
        self.assertEqual(len(result["job_ids"]), 1)

    def test_wildcard_seed_is_passive_only(self):
        e = self.app.save_engagement(dict(name="Wildcard fixture", scope="*.wildcard.test", authorized=True))
        self.assertEqual(self.app.workflow_targets(e, "hosts"), [])
        self.assertEqual(self.app.workflow_targets(e, "passive"), ["wildcard.test"])
        for tool in ("subfinder", "urlfinder"):
            command(e, dict(tool=tool, target="wildcard.test"), self.tools)
        with self.assertRaises(ValueError):
            target_url("wildcard.test", e)
        with self.assertRaises(ValueError):
            command(e, dict(tool="httpx", target="wildcard.test"), self.tools)


if __name__ == "__main__":
    unittest.main()
