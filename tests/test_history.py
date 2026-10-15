import tempfile
import unittest

from dashboard.server import App


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.app = App(self.directory.name)
        self.e = self.app.save_engagement(dict(name="History fixture", scope="example.test", authorized=True))
        self.other = self.app.save_engagement(dict(name="Other fixture", scope="other.test", authorized=True))

    def tearDown(self):
        self.app.shutdown()
        self.app.db.close()
        self.directory.cleanup()

    def job(self, key="fixture", engagement=None, status="completed"):
        e = engagement or self.e
        job = dict(id=key, engagement_id=e["id"], status=status, tool="httpx", target="https://" + e["scope"][0], finished="2026-10-15T00:00:00+00:00")
        self.app.put("job", job)
        log = self.app.logpath(job)
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text("local fixture output")
        return job

    def test_confirmation_is_required_and_changes_nothing_on_rejection(self):
        job = self.job()
        for confirmed in (None, False, "true", 1):
            with self.subTest(confirmed=confirmed), self.assertRaisesRegex(ValueError, "Confirm"):
                self.app.erase_history(dict(confirmed=confirmed))
        self.assertTrue(self.app.logpath(job).exists())
        self.assertEqual(len(self.app.all("job")), 1)

    def test_scoped_erasure_preserves_other_history_and_engagement_data(self):
        job = self.job()
        other = self.job("other", self.other)
        self.app.put("workflow", dict(id="workflow", engagement_id=self.e["id"], status="completed"))
        for kind in ("auth", "asset", "finding", "reference", "traffic_gate"):
            self.app.put(kind, dict(id="preserved", engagement_id=self.e["id"], marker=kind))
        before = {kind: self.app.all(kind) for kind in ("engagement", "auth", "asset", "finding", "reference", "traffic_gate")}
        result = self.app.erase_history(dict(confirmed=True, engagement_id=self.e["id"]))
        self.assertEqual((result["jobs_deleted"], result["workflows_deleted"]), (1, 1))
        self.assertEqual(self.app.all("job"), [other])
        self.assertEqual(self.app.all("workflow"), [])
        self.assertFalse(self.app.logpath(job).exists())
        self.assertTrue(self.app.logpath(other).exists())
        self.assertEqual(before, {kind: self.app.all(kind) for kind in before})
        self.assertEqual(self.app.all("completed_run")[0]["id"], self.app.run_key(job))

    def test_all_history_includes_orphan_logs_and_is_idempotent(self):
        self.job()
        self.job("other", self.other)
        orphan = self.app.data / "jobs" / "orphan" / "session.json"
        orphan.parent.mkdir()
        orphan.write_text("local obsolete fixture")
        self.app.erase_history(dict(confirmed=True))
        self.assertFalse((self.app.data / "jobs").exists())
        self.assertEqual(self.app.all("job"), [])
        self.assertEqual(len(self.app.all("engagement")), 2)
        self.assertEqual(self.app.erase_history(dict(confirmed=True))["jobs_deleted"], 0)

    def test_active_jobs_and_workflows_block_erasure(self):
        for status in ("queued", "running", "cancelling"):
            job = self.job(status=status)
            with self.assertRaisesRegex(ValueError, "active"):
                self.app.erase_history(dict(confirmed=True))
            self.assertTrue(self.app.logpath(job).exists())
        self.job(status="completed")
        self.app.put("workflow", dict(id="active", engagement_id=self.e["id"], status="running"))
        with self.assertRaisesRegex(ValueError, "active"):
            self.app.erase_history(dict(confirmed=True, engagement_id=self.e["id"]))
        # Other engagements can still erase their inactive history.
        self.job("other", self.other)
        self.app.erase_history(dict(confirmed=True, engagement_id=self.other["id"]))
        self.assertEqual(len(self.app.all("job")), 1)
        self.app.put("workflow", dict(id="active", engagement_id=self.e["id"], status="cancelled"))

    def test_erased_cancelled_queue_keys_do_not_break_the_worker(self):
        self.job(status="cancelled")
        self.app.erase_history(dict(confirmed=True))
        self.app.execute("fixture")
        self.assertTrue(self.app.worker.is_alive())
        self.assertEqual(self.app.all("job"), [])


if __name__ == "__main__":
    unittest.main()
