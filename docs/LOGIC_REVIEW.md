# Business logic review — 2026-10-15

Reviewed local engagement changes, scope rules, session binding, duplicate runs,
queue state, scanner output, finding review/export, traffic feedback, and public
reference handling. Verification uses temporary workspaces, fake executables,
browser fixtures and loopback HTTP services. No engagement scans are required.

## Corrected workflows

| Issue | Result after correction |
|---|---|
| A caller-supplied session revision could change a duplicate-run key. | Enqueue derives the revision from the saved session and ignores caller revisions. |
| DNS and TLS adapters discarded URL components that still changed their duplicate keys. | Keys use the adapter's effective host or host/port target. |
| Default HTTPS/HTTP ports could cause equivalent session origins to mismatch. | Origin comparison normalizes default ports and IPv6 authorities; different schemes and non-default ports remain separate. |
| Session URLs silently lost paths, queries or fragments. | Only origin URLs, optionally ending in `/`, can be saved as session bindings. |
| Session replacement/deletion and finding review could interleave with enqueue or scope changes. | These mutations use the same application lock as enqueue and engagement edits. Session snapshots and their recorded revisions stay consistent. |
| Scanner status spelling differences bypassed block feedback or cache filtering. | Feedback, cache extraction and summaries share status parsing for supported JSON aliases. |
| Repeated Nuclei observations created duplicate findings; out-of-scope and malformed observations could enter the findings list. | Scanner finding IDs bind engagement, template, target, matcher and session. Targets are scope checked, metadata is normalized, and repeat observations retain human review and provenance. |
| Output-processing failures could change a successful tool execution into a failed job after its completion marker was stored. | Process outcome remains intact; incomplete output processing gets a separate warning. |
| Editing scope left the generated scope checklist stale. | The checklist is regenerated, retaining checkmarks for unchanged rules. Handoff and feature coverage remain intact. |
| Policy/scope edits invalidated live readiness but left exported finding reviews marked ready. | Edits regenerate finding exports against current scope/policy. JSON exports include their evaluation timestamp. Recorded historical finding status is preserved. |
| Bare IPv6 scope addresses could not be used as targets. | Bare IPv6 addresses normalize to bracketed URL authorities. |

## Boundaries retained

- Readiness checks assess evidence completeness and reviewer assertions. They do
  not prove exploitability, predict platform outcomes, or submit reports.
- Exported reviews are timestamped snapshots. Time-dependent policy freshness
  must be checked again in the dashboard before submission.
- Scanner block detection depends on statuses actually emitted by the tool.
  It cannot interpret every WAF challenge or hidden HTTP response.
- URL-only scope is stored but current scan adapters require whole-host scope.
  Hosts with URL exclusions cannot be scanned by these adapters.
- Cached observations are historical evidence. They do not authorize a new run;
  every new run must pass current scope and session checks.
- Deleting a saved session does not revoke credentials already snapshotted for
  queued jobs. Cancel those jobs separately.
- Repeat scanner observations preserve human dispositions. A dismissed finding
  should be re-reviewed when new evidence or program behavior warrants it.

Regression coverage: `tests/test_business_logic.py`, alongside scope, readiness,
installation, traffic, browser, and loopback integration checks.
