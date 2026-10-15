"""Lightweight Linux/WSL process sampling; no third-party dependencies."""
import os
from pathlib import Path
import threading
import time


def process_sample(pid):
    root = Path("/proc") / str(pid)
    try:
        raw = (root / "stat").read_text()
        fields = raw[raw.rfind(")") + 2:].split()
        values = dict(pid=pid, start=fields[19], cpu_seconds=(int(fields[11]) + int(fields[12])) / os.sysconf("SC_CLK_TCK"),
                      rss_bytes=int(fields[21]) * os.sysconf("SC_PAGE_SIZE"), threads=int(fields[17]), read_bytes=0, write_bytes=0)
        try:
            status = dict(line.split(":", 1) for line in (root / "status").read_text().splitlines())
            values["peak_rss_bytes"] = int(status.get("VmHWM", "0 kB").split()[0]) * 1024
        except (OSError, ValueError):
            values["peak_rss_bytes"] = values["rss_bytes"]
        try:
            io = dict(line.split(":", 1) for line in (root / "io").read_text().splitlines())
            values.update(read_bytes=int(io.get("read_bytes", 0)), write_bytes=int(io.get("write_bytes", 0)))
        except (OSError, ValueError):
            pass
        return values
    except (OSError, ValueError, IndexError):
        return None


def dashboard_metrics():
    sample = process_sample(os.getpid())
    if not sample:
        return dict(available=False, reason="Live process metrics require Linux /proc")
    try:
        descriptors = len(list((Path("/proc") / str(os.getpid()) / "fd").iterdir()))
    except OSError:
        descriptors = None
    return dict(available=True, rss_mb=round(sample["rss_bytes"] / 1048576, 2), peak_rss_mb=round(sample["peak_rss_bytes"] / 1048576, 2), cpu_seconds=round(sample["cpu_seconds"], 2),
                threads=sample["threads"], open_fds=descriptors, read_mb=round(sample["read_bytes"] / 1048576, 2), write_mb=round(sample["write_bytes"] / 1048576, 2))


class ProcessMonitor:
    def __init__(self, pid, interval=0.5):
        self.pid = pid
        self.interval = interval
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.observed = {}
        self.started = time.monotonic()
        self.last_cpu = 0
        self.last_clock = self.started
        self.values = dict(available=True, rss_mb=0, peak_rss_mb=0, cpu_seconds=0, cpu_percent=0, read_mb=0, write_mb=0,
                           processes=0, peak_processes=0, samples=0, interval_seconds=interval)
        self.sample()
        self.worker = threading.Thread(target=self.work, daemon=True)
        self.worker.start()

    def sample(self):
        pending = [self.pid]
        visited = set()
        current = []
        while pending and len(visited) < 512:
            pid = pending.pop()
            if pid in visited:
                continue
            visited.add(pid)
            sample = process_sample(pid)
            if sample:
                current.append(sample)
                try:
                    pending += [int(p) for p in (Path("/proc") / str(pid) / "task" / str(pid) / "children").read_text().split()]
                except (OSError, ValueError):
                    pass
        with self.lock:
            for item in current:
                self.observed[(item["pid"], item["start"])] = item
            cpu = sum(item["cpu_seconds"] for item in self.observed.values())
            rss = sum(item["rss_bytes"] for item in current) / 1048576
            clock = time.monotonic()
            percent = max(0, cpu - self.last_cpu) / max(clock - self.last_clock, 0.001) * 100 if self.values["samples"] else 0
            self.last_cpu, self.last_clock = cpu, clock
            self.values.update(rss_mb=round(rss, 2), peak_rss_mb=round(max(rss, self.values["peak_rss_mb"]), 2),
                               cpu_seconds=round(cpu, 3), cpu_percent=round(percent, 1),
                               read_mb=round(sum(item["read_bytes"] for item in self.observed.values()) / 1048576, 2),
                               write_mb=round(sum(item["write_bytes"] for item in self.observed.values()) / 1048576, 2),
                               processes=len(current), peak_processes=max(len(current), self.values["peak_processes"]), samples=self.values["samples"] + 1)
            if not current and not self.observed:
                self.values["available"] = False

    def snapshot(self):
        with self.lock:
            return dict(self.values)

    def work(self):
        while not self.stop.wait(self.interval):
            self.sample()

    def close(self):
        if not self.stop.is_set():
            self.stop.set()
            self.worker.join(timeout=1)
            self.sample()
        return self.snapshot()
