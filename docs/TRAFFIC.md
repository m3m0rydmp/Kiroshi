# Traffic controls and WAF behavior

Kiroshi exposes bounded controls on supported adapters. It is **not a general WAF
evasion or exploitation framework**. A browser User-Agent alone does not reproduce
a browser's TLS fingerprint, JavaScript behavior, cookies or application state.
Challenges and access denials are recorded as observations, not confirmed WAF
attribution or vulnerabilities.

## Engagement settings

In **Edit scope → Traffic & block-response controls**, configure:

- The engagement request-rate ceiling (1–100/sec) and maximum job duration.
- Tool worker concurrency (1–10) and request timeout (3–60 seconds).
- Whether to stop on observable block signals (enabled by default).
- Monitored statuses (429 and 503 by default; optionally 403).
- Consecutive observed signals before stopping and minimum cooldown duration.

The defaults are a ceiling of 5/sec, one worker, a 10-second request timeout, stop
on the first observed 429/503, and a 30-second cooldown. A 403 can simply be an
expected authorization denial; enable that monitor only when it fits the program.
503 may also indicate ordinary service unavailability. Neither establishes a WAF.

In **New run → Run pacing**, select inherited settings or **Gentle** (1/sec and one
worker), set a lower run rate, and use supported extra delay/jitter controls. A run
cannot raise the engagement rate ceiling. Gentle clears optional delay/jitter so it
can be used across protocols. Command previews show effective pacing before queueing.

## Adapter support

| Adapter | Rate control | Worker control | Extra delay / jitter | Block feedback |
|---|---|---|---|---|
| URLFinder | Native global/provider HTTP rate | Provider internals remain tool-managed | Unsupported | No general target status stream |
| Subfinder | Native provider HTTP rate | Provider internals remain tool-managed | Unsupported | No general status stream; provider errors may be hidden |
| dnsx | Native DNS query rate | DNS threads | Unsupported | DNS has no HTTP/WAF response status |
| httpx | Native request rate | Threads | Delay in milliseconds; no jitter | Emitted JSON statuses; response headers included |
| tlsx | Serial TLS connection pacing | Intentionally one worker | Delay, at least the rate-derived interval; no jitter | TLS handshakes have no HTTP status |
| Katana | Native request rate | Fetchers; one input | Delay rounded **up** to whole seconds; no jitter | Emitted response JSON and headers |
| Feroxbuster | Per-directory rate; recursion off and one scan | Threads | Unsupported | Emitted JSON; native auto-bail (stop mode) or auto-tune (observe mode) |
| ffuf | Native request rate | Threads | Delay and a bounded random delay range | Emitted JSON statuses; all response codes are included |
| Nuclei | Native request rate | Template concurrency; one target | Unsupported | Only findings/output that expose a status; not every request |

Unsupported controls are disabled in the UI and rejected by the API rather than
silently ignored. Fixed delays plus rate limits are ceilings, not throughput promises.
Fewer threads, scan startup, DNS resolution, response times and native tool behavior
can reduce the actual rate. Source-side requests and in-flight requests are not
controlled by a network firewall. There is one dashboard scan worker globally.

Retries are disabled for the active HTTP adapters where supported. Subfinder, URLFinder and
other provider internals can have their own behavior. Nuclei currently uses only
the bundled inventory template, so none of this implies general exploit support.

## What happens when a response is blocked

The runner reads structured scanner output. If an emitted status matches the selected
policy, it records an event. With stop enabled and the threshold reached, it kills
the current process group and marks the job `rate_limited` (429) or `blocked`.
Requests already in flight cannot be undone.

Queued HTTP jobs for the same **engagement and exact origin** wait for the cooldown;
other origins and DNS/TLS work are not placed under that hold. The stopped job is
never automatically retried. Partial output and cache entries remain available.

When a scanner exposes `Retry-After`, its numeric delay or HTTP date is respected
if longer than the configured minimum. A server wait over 24 hours produces a
manual hold instead of silently shortening it. When the header is unavailable or
invalid, the configured minimum applies. Output filtering/buffering and scanner
limitations mean some responses are never visible: this is best-effort feedback,
not a guarantee that every block is observed. No preflight probes are added.

**Jobs & logs → Traffic cooldowns** shows active holds. To clear one early, open
**Review hold** and record why a retest is appropriate; clearing lets queued jobs
resume. Otherwise wait, lower rates, or request program-approved allowlisting or
test access. Turning stop off records observed signals without automatically halting
the job; it should only be used when compatible with the program's rules.

Job settings are snapshotted when queued. Cancel pending jobs before editing an
engagement's settings, then queue new runs with the lower rate; clearing a hold does
not rewrite queued command flags. A process exiting successfully means the command
finished, not that coverage is complete or that no requests were blocked internally.

## Headers, sessions and limits

HTTP adapters use the configured Chrome-style User-Agent. Add legitimate
program-required identification headers using an exact-origin saved session; a
cookie is optional if headers alone are needed. Existing header values remain
private. The passive source clients in Subfinder and URLFinder use their own browser User-Agents for provider
requests; individual provider clients remain tool-managed.

The dashboard does not automatically rotate IPs/proxies, forge routing headers,
solve CAPTCHAs, mutate exploit payloads, bypass authorization, or retry through other
assets. Burp/proxy routing and transport impersonation are not configured by this
version. If a program permits a specific testing technique, it needs an explicit
adapter with corresponding scope/evidence controls rather than an arbitrary flags box.

Terminal-launched agent tools and other terminals are outside this runner's traffic
governor. Shared agent instructions request compliance but cannot enforce external
process behavior. Scan permissions and acceptable request rates come from the
program policy, not from a technical bypass being possible.
