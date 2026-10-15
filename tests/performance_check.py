"""Isolated populated-dashboard benchmark; never queues scanners or sends webhooks."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import signal
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time
from urllib.request import Request, urlopen

from dashboard.http_identity import browser_user_agent
from dashboard.performance import process_sample
from dashboard.tools import ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-rss-mb", type=float, default=256)
    parser.add_argument("--max-p95-ms", type=float, default=500)
    parser.add_argument("--assets", type=int, default=1000, help="Synthetic asset count (1–100000)")
    args = parser.parse_args()
    if not 1 <= args.assets <= 100000:
        parser.error("--assets must be between 1 and 100000")
    with tempfile.TemporaryDirectory(prefix="kiroshi-performance-") as directory:
        data = Path(directory)
        server = subprocess.Popen([sys.executable, "-u", "-m", "dashboard.server", "--port", "0", "--data-dir", str(data)], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            line = server.stdout.readline()
            match = re.search(r"http://127\.0\.0\.1:[0-9]+", line)
            if not match:
                raise RuntimeError("Benchmark server did not start")
            base = match[0]
            stamp = datetime.now(timezone.utc).isoformat()
            engagement = dict(id="fixture", name="Performance fixture", scope=["127.0.0.1"], excluded=[], authorized=True, policy="Local fixture only", rate=5, duration=10, provider="claude", created=stamp, updated=stamp)
            records = [("engagement", "fixture", json.dumps(engagement))]
            for number in range(200):
                key = f"fixture-{number:04}"
                job = dict(id=key, engagement_id="fixture", tool="httpx", target=f"http://127.0.0.1/{number}", status="completed", created=stamp, started=stamp, finished=stamp, returncode=0, duration=10, display="local fixture", identity="Anonymous")
                records.append(("job", key, json.dumps(job)))
                log = data / "jobs" / key / "output.log"
                log.parent.mkdir(parents=True)
                log.write_text("local fixture observation\n" * 40)
            for number in range(args.assets):
                key = f"asset-{number}"
                asset = dict(id=key, engagement_id="fixture", value=f"http://127.0.0.1/path/{number}", tool="httpx", identity="Anonymous", job_ids=["fixture-0000"], detail={"status_code": 200, "body": "local evidence fixture " * 30})
                records.append(("asset", key, json.dumps(asset)))
            connection = sqlite3.connect(data / "kiroshi.sqlite3")
            try:
                connection.executemany("INSERT INTO records VALUES (?,?,?)", records)
                connection.commit()
            finally:
                connection.close()

            def request(path):
                begin = time.perf_counter()
                with urlopen(Request(base + path, headers={"User-Agent": browser_user_agent()}), timeout=20) as response:
                    body = response.read()
                return (time.perf_counter()-begin)*1000, len(body), body

            state = json.loads(request("/api/state")[2])  # Warm tool discovery and imported asset index.
            assert state["asset_counts"]["total"] == args.assets
            assert len(state["assets"]) <= 10
            assets = json.loads(request("/api/assets?limit=50")[2])
            assert assets["total"] == args.assets and len(assets["items"]) <= 50
            assert "local evidence fixture" not in json.dumps(assets)
            before = json.loads(request("/api/performance")[2])
            first = process_sample(server.pid)
            paths = ["/api/state", "/api/performance", "/api/jobs/fixture-0000/log", "/api/assets?limit=50", "/api/assets?limit=50&q=path%2F12"] * 18
            started = time.perf_counter()
            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(request, paths))
            duration = time.perf_counter()-started
            last = process_sample(server.pid)
            after = json.loads(request("/api/performance")[2])
            latencies = sorted(result[0] for result in results)
            peak = last["peak_rss_bytes"] / 1048576
            p95 = latencies[math.ceil(len(latencies)*.95)-1]
            report = dict(recorded_at=stamp, fixture=dict(jobs=200, assets=args.assets, asset_page_size=50, requests=len(paths), concurrency=4, network="loopback only; no scanners or notifications executed"),
                          latency_ms=dict(median=round(statistics.median(latencies), 2), p95=round(p95, 2), maximum=round(max(latencies), 2)),
                          duration_seconds=round(duration, 2), backend_peak_rss_mb=round(peak, 2), backend_rss_mb=after["rss_mb"],
                          backend_cpu_seconds=round(last["cpu_seconds"]-first["cpu_seconds"], 3), open_fds_before=before["open_fds"], open_fds_after=after["open_fds"],
                          response_megabytes=round(sum(result[1] for result in results)/1048576, 2),
                          budgets=dict(max_rss_mb=args.max_rss_mb, max_p95_ms=args.max_p95_ms),
                          passed=peak <= args.max_rss_mb and p95 <= args.max_p95_ms and after["open_fds"] <= before["open_fds"] + 4,
                          notice="Local synthetic regression check. Scanner peaks and production-scale histories require separate measurement. CPU and memory sampling can miss short-lived child processes.")
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps(report, indent=2))
            if not report["passed"]:
                raise SystemExit(1)
        finally:
            server.send_signal(signal.SIGINT)
            server.wait(timeout=10)
            server.stdout.close()
            server.stderr.close()


if __name__ == "__main__":
    main()
