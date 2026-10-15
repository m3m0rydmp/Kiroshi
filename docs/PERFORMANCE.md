# Performance verification

Overview shows backend resident memory, kernel peak RSS, cumulative CPU time,
threads, open file descriptors, disk I/O, and notification queue depth. Refresh
the snapshot with **Refresh metrics**. These are Linux/WSL `/proc` measurements;
browser memory is separate.

Running jobs sample their scanner process tree every 0.5 seconds. Live logs show
sampled peak RSS, CPU time, current CPU percentage, disk reads/writes and peak
process count. Final samples are retained with the job. CPU percentages use one
core as 100%, so parallel tools can exceed 100%. Summed process RSS can count
shared pages more than once. Sampling can miss brief peaks or short-lived children
and is not a memory quota or network firewall.

## Repeatable local benchmark

```bash
python3 -m tests.performance_check --output /tmp/kiroshi-performance.json
```

This starts a separate temporary backend and populates 200 completed fixture jobs,
1,000 cached assets and fixture logs. It warms binary detection, then sends 90
loopback API requests with four concurrent clients, measuring state retrieval,
log reads and performance snapshots. It does not queue scans, use saved engagement
data, or send webhook notifications.

Default regression budgets are 256 MB peak backend RSS, 500 ms API p95, and no
unexplained growth beyond four file descriptors. Tune the first two with
`--max-rss-mb` and `--max-p95-ms` when testing another environment.

Measured locally on 2026-10-16 (Asia/Singapore):

| Measurement | Result |
|---|---:|
| Backend peak RSS | 37.83 MB |
| Backend RSS after requests | 36.78 MB |
| Median API latency | 12.34 ms |
| p95 API latency | 107.65 ms |
| Maximum API latency | 127.21 ms |
| Backend CPU during load | 0.99 seconds |
| Wall time during load | 0.78 seconds |
| Open file descriptors before / after | 7 / 7 |
| Response data transferred | 8.80 MB |

The browser fixture measured 1.96 MB of JavaScript heap after the tested UI flows;
that excludes Chrome's native memory and is a different fixture from the API load
test. These results are local regression evidence, not production-scale guarantees.
Large retained logs, larger histories and real scanners require separate checks.

History erasure, event dispatch and resource-monitor shutdown have regression
tests. Notification delivery uses a separate bounded worker, an eight-second HTTP
timeout and no automatic retries, so a slow receiver does not block scan execution.
