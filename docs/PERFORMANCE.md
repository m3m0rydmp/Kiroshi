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
python3 -m tests.performance_check --assets 25000 --output /tmp/kiroshi-assets-25000.json
```

This starts a separate temporary backend and populates 200 completed fixture jobs,
1,000 cached assets and fixture logs. It warms binary detection, then sends 90
loopback API requests with four concurrent clients, measuring state retrieval,
log reads, indexed asset pages/search and performance snapshots. The `--assets`
option accepts up to 100,000 synthetic assets; it changes only the isolated fixture. It does not queue scans, use saved engagement
data, or send webhook notifications.

Default regression budgets are 256 MB peak backend RSS, 500 ms API p95, and no
unexplained growth beyond four file descriptors. Tune the first two with
`--max-rss-mb` and `--max-p95-ms` when testing another environment.

Measured locally on 2026-10-16 (Asia/Singapore):

| Measurement                          |       Result |
| ------------------------------------ | -----------: |
| Backend peak RSS                     |     37.83 MB |
| Backend RSS after requests           |     36.78 MB |
| Median API latency                   |     12.34 ms |
| p95 API latency                      |    107.65 ms |
| Maximum API latency                  |    127.21 ms |
| Backend CPU during load              | 0.99 seconds |
| Wall time during load                | 0.78 seconds |
| Open file descriptors before / after |        7 / 7 |
| Response data transferred            |      8.80 MB |

The browser fixture measured 1.96 MB of JavaScript heap after the tested UI flows;
that excludes Chrome's native memory and is a different fixture from the API load
test. These results are local regression evidence, not production-scale guarantees.
Large retained logs, larger histories and real scanners require separate checks.

History erasure, event dispatch and resource-monitor shutdown have regression
tests. Notification delivery uses a separate bounded worker, an eight-second HTTP
timeout and no automatic retries, so a slow receiver does not block scan execution.

## Large-cache regression

After paginating asset access, a 25,000-asset fixture with 200 historical jobs passed
the same budgets on 2026-10-16 (Asia/Singapore). Its 90 requests included asset-page
queries and global searches alongside dashboard polling and log reads.

| Measurement                                 |            Result |
| ------------------------------------------- | ----------------: |
| Backend peak RSS (including index backfill) |          59.23 MB |
| Median / p95 API latency                    | 21.04 / 102.46 ms |
| Maximum API latency                         |         125.94 ms |
| Open file descriptors before / after        |             7 / 7 |
| Response data transferred                   |           2.45 MB |

General state responses contain ten asset summaries and accurate totals; asset pages
contain at most 200 summaries and omit raw scanner evidence. The browser check verifies
50-row pagination, searches beyond the current page, source/status controls and lazy
evidence access. The derived SQLite index is maintained with asset writes, while
existing evidence records retain their IDs and contents.
