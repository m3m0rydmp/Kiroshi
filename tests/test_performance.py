import os
import time
import unittest

from dashboard.performance import ProcessMonitor, dashboard_metrics, process_sample


@unittest.skipUnless(os.path.isdir("/proc"), "Linux /proc required")
class PerformanceTests(unittest.TestCase):
    def test_dashboard_metrics_are_positive_and_missing_process_is_safe(self):
        metrics = dashboard_metrics()
        self.assertTrue(metrics["available"])
        self.assertGreater(metrics["rss_mb"], 0)
        self.assertGreaterEqual(metrics["peak_rss_mb"], metrics["rss_mb"] - 1)
        self.assertGreater(metrics["threads"], 0)
        self.assertIsNone(process_sample(999999999))

    def test_monitor_samples_then_stops_without_leaking_a_thread(self):
        monitor = ProcessMonitor(os.getpid(), interval=.01)
        try:
            time.sleep(.04)
            sample = monitor.snapshot()
            self.assertGreaterEqual(sample["samples"], 2)
            self.assertGreater(sample["peak_rss_mb"], 0)
            self.assertGreater(sample["processes"], 0)
        finally:
            final = monitor.close()
        self.assertFalse(monitor.worker.is_alive())
        self.assertGreaterEqual(final["peak_rss_mb"], sample["peak_rss_mb"])
        self.assertEqual(monitor.close(), final)


if __name__ == "__main__":
    unittest.main()
