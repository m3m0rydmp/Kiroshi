# Kiroshi dashboard

A local WSL engagement console built on [0xcucumbersalad/hunt](https://github.com/0xcucumbersalad/hunt).
The original `hunt` CLI is retained. The dashboard invokes that actual script for
each engagement, keeps its brief as a methodology reference, and supplies bounded
shared instructions for Claude Code and Codex.

The interface uses moonlight cyan, lavender, violet, and peach/coral sunset colors.
There are no remote fonts, analytics, CDNs, or image dependencies.

## Start in WSL

For a fresh machine, follow [installation and tool setup](docs/INSTALL.md).
Tool paths shown by the UI are detected locally; they are not required paths.

Requires Python 3.10+ and Bash. No Python packages, Node build, Docker, or model API
keys are required to run the dashboard itself.

```bash
cd Kiroshi  # your cloned checkout
./kiroshi
```

Open **http://localhost:8741** from your Windows browser. If WSL localhost forwarding
is disabled, enable that forwarding; do not expose this service on a public interface.
The process binds to IPv4 loopback only. Stop it with Ctrl+C.

```bash
./kiroshi --port 8742 --data-dir ~/.local/share/kiroshi
```

## Engagement workflow

1. Create an engagement. Enter the program policy URL separately from explicit
   in-scope hostnames/IPs and excluded hosts. `*.example.com` covers subdomains,
   not the apex. Root HTTP(S) URLs (including wildcard URLs) normalize to host
   rules. URLs with paths or explicit ports retain those boundaries. Current scan
   adapters require whole-host authorization and refuse hosts with URL exclusions;
   URL-only rules can be saved but cannot be scanned yet. CIDR and mobile-app
   rules remain unsupported. Do not broaden scope to bypass an adapter limitation.
2. Choose a ready tool, enter an authorized target, preview, then queue an anonymous
   run. Nothing runs just because you entered a domain or created an engagement.
3. Results remain in the local cache and per-run logs across browser/server restarts.
   The normalized cache includes supported JSON URL/host observations and scoped
   Subfinder names. All runs retain capped text logs even when normalization finds
   no assets. Excluded discoveries are not promoted into the asset cache.
   Newly parsed 404/410 misses and 429/503 responses remain in logs rather than
   becoming discovered assets.
4. On the engagement page, add a named session: exact origin, Cookie header value,
   and optional `Name: Value` headers such as Authorization or X-CSRF-Token.
   Use separate profiles for Account A, Account B, and different roles.
5. Select **Run on asset** in the cache, choose an HTTP tool and that session.
   Prior anonymous evidence is preserved; a new job records its own identity.
   This explicitly runs a new request set; it does not merely relabel cached data.
6. Replace expired credentials at any time. Replacement affects future jobs;
   queued jobs retain their credential snapshot. Deleting a saved session also
   leaves already-queued snapshots intact. Cancel those jobs separately if needed.
7. Review observations in Findings. Scanner observations begin unverified.
   Manual findings support notes, evidence references, severity, and triage status.

Jobs are serialized globally, with per-tool rate limits and a wall-clock timeout.
One active tool prevents independent dashboard runs multiplying the configured rate.
Tool protocols may make auxiliary DNS/TLS/provider requests; the configured rate is
not a network firewall or a hard packet budget. Log capture stops at 10 MiB and the
job is terminated. Interrupted jobs are marked after a server restart, not rerun.

## Tools

The catalog detects 36 common executables from PATH and standard WSL Go/Cargo/local
binary directories. Toolchain supports absolute executable path overrides. It does
not install, update, or automatically execute discovered tools.

Nine adapters:

| Tool | Initial runnable profile |
|---|---|
| Subfinder | Passive discovery for a selected in-scope seed hostname |
| dnsx | A / AAAA / CNAME inventory |
| URLFinder | Scoped passive URL discovery from public sources |
| httpx | Selected-scheme status/title/technology inventory, no redirects |
| tlsx | Certificate / TLS inventory on selected port or 443 |
| Katana | Non-headless, depth-two crawl confined to the selected origin |
| Feroxbuster | Non-recursive GET discovery, small bundled wordlist |
| ffuf | GET path discovery, small bundled wordlist |
| Nuclei | Bundled server-header inventory template only |

Other entries are **inventory-only**, including Amass, Findomain, assetfinder, Chaos,
gau, waybackurls, puredns, shuffledns, dnsgen, alterx, Naabu, Nmap, Arjun,
ParamSpider, Dalfox, sqlmap, crlfuzz, Interactsh, Gitleaks, TruffleHog, jq, anew, uro,
unfurl, Notify, Claude Code, and Codex. They need a reviewed adapter before dashboard
execution. There is no arbitrary shell-command input.

Add executable metadata and a bounded argv builder in `dashboard/tools.py`, then
exercise it against a local fixture. Add a normalizer where useful. Confirm flags
against the installed tool version. Authenticated adapters also need private-file
header support and exact-origin behavior; never persist credentials in the job argv.

Subfinder uses an isolated home, so your existing provider API-key config is not
loaded in this version. Broad Nuclei template selection, custom wordlists, port-scan
execution and archive import from other inventory tools are not implemented.
The dashboard does not currently configure Burp MCP or HTTP Workbench MCP.

## Sessions and local security

Session values are stored in plaintext JSON files under `.kiroshi-data/secrets/` with
mode 0600. They are not encrypted at rest; use disk encryption if required. The API
returns labels, exact origins and header names, never saved values. No credentials
are put in browser localStorage or persisted job command metadata. Private per-job
configuration/request files pass headers to tools, then are removed after execution
or cancellation. Restart recovery removes abandoned private job files.

Known complete header values are redacted from captured stdout, including their
JSON-escaped form. This is a convenience, not comprehensive evidence sanitization:
responses, partial/reflected tokens, URLs, and derived secrets may still be sensitive.
Treat the entire data directory as private and review evidence before sharing it.

HTTP sessions are bound to an exact scheme, hostname and explicit port; equivalent
implicit/explicit default ports should be entered consistently. Redirects are
disabled. Katana is confined to the selected origin, and Feroxbuster cannot recurse
or extract further links. Host routing/framing headers cannot be overridden.

Scope checks occur before queuing; tool defaults/configuration are isolated using
a private HOME/XDG directory and a restricted environment. These checks do not
provide a network-level sandbox: DNS rebinding, tool bugs or custom executable
overrides can violate assumptions. Run only locally with trusted installed binaries
and program-approved options. Do not expose this service through a tunnel.

The server rejects unrecognized Host headers, cross-site requests, and cross-origin
mutations. Writes require a per-process request token. It is a single-user local
service, without login, TLS or multi-user isolation; other local processes are trusted.

## Claude Code / DeepSeek and Codex

Open **Agent handoff**, save your current position and copy the terminal command.
The engagement has `AGENTS.md`, `CLAUDE.md`, `scope.json`, and persistent state files.
Your configured Claude Code endpoint/model or Codex credentials remain managed by
the respective CLI. The dashboard itself does not send requests to model providers.

Agent execution is **terminal-based** in this version; the web UI does not launch
an unattended agent or stream its conversation. Saved dashboard sessions are not
automatically injected into agent processes. Only one agent should act on the
engagement at a time. Use the handoff rather than relying on cross-provider chat history.

## Report readiness and public report references

Open **Findings → Review** to record policy eligibility, reproduction attempts,
prerequisites, control comparisons, sanitized request/response evidence, security
boundary, demonstrated impact, false-positive checks, public duplicate searches,
severity reasoning and remediation. **Check readiness** previews the result without
saving. Drafts can be saved with gaps; **confirmed** and **reported** require all
checks and a named reviewer attestation. Marking reported is local bookkeeping;
nothing is submitted to HackerOne.

Dispositions are `needs_evidence`, `likely_informational`,
`likely_excluded_or_expected`, and `ready_for_human_review`. They are local review
assessments, not HackerOne states. These deterministic checks assess text completeness,
scope rules and the reviewer's assertions; they do not semantically verify evidence,
replay exploits, predict acceptance, or eliminate undisclosed duplicates. A 30-day
policy-review reminder is a local rule, not HackerOne policy. Changed finding content,
scope or policy invalidates the earlier attestation. Existing legacy finding statuses
are retained, but their current readiness shows any missing/stale review.

Open **Public reports → Import public reports** and paste up to five public
HackerOne report URLs or IDs. The collector anonymously fetches the site's public
report JSON, accepts only explicit public+disclosed records, and stores source URLs,
historical outcomes, disclosure/retrieval dates, visible bounty/currency, weakness,
a source fingerprint and a short attributed excerpt (at most 100 words / 1200 chars).
No private reports, attachments or full discussion threads are collected. Imports
are cached; select refresh for an explicit re-fetch. Requests are serialized at most
once per second, have response-size/time limits, and stop on errors/access controls.
The website's public JSON representation is not the documented Hacker API and may
change; failures are shown per report without attempting a bypass.

Filter the library by visible rewards, triaged/resolved, or informative/not applicable
outcomes. Unknown rewards remain unknown. Link references to a finding, or examine
explainable lexical matches based on title/boundary terms and weakness. Matches and
reward amounts never increase readiness or severity. A historical reward does not
establish present eligibility: check this target's current asset/class exclusions,
required evidence, account privileges and policy. Public disclosures have selection
bias and may be incomplete/outdated.

Optional **Search HackerOne API** uses the documented Hacktivity endpoint, retrieves
10 results per explicit page request, forces `disclosed:true`, and locally rejects
non-disclosed results. It needs separate HackerOne API credentials in the server
environment (not engagement cookies):

```bash
export KIROSHI_H1_API_USERNAME='your-api-username'
read -rs KIROSHI_H1_API_TOKEN
export KIROSHI_H1_API_TOKEN
./kiroshi
```

Enter the token at the hidden shell prompt. Tokens are not stored in the dashboard
database or sent to report pages. Search accepts documented Lucene filters such as
`team:gitlab AND total_awarded_amount:>0`; program outcomes are historical context.
Search only discovers candidates; click Import to fetch a disclosed report anonymously.

Generated and existing engagement workspaces receive `QUALITY.md` and a bounded
`public-references.json` index. Finding reviews also export Markdown and `.review.json`
files. Shared agent instructions explicitly treat references as untrusted data,
require independent target evidence and override blanket upstream dismissals of
information-disclosure classes. This is retrieval/context guidance, not model training
or an autonomous AI triage service.

Reference methodology: [HackerOne report states](https://docs.hackerone.com/en/articles/8475030-report-states),
[Hacktivity API](https://api.hackerone.com/hacker-resources/#get-hacktivity),
[trial-report restrictions](https://docs.hackerone.com/en/articles/8474047-restricted-from-submissions).

## Browser User-Agent

httpx, Katana, Feroxbuster, ffuf, Nuclei, and the public-reference collector use a
consistent Linux Chrome-style User-Agent. The Chrome major version is detected from
the installed browser; without Chrome it falls back to major 154. Set `KIROSHI_USER_AGENT`
before starting the server to select a different single-line browser User-Agent.
Session-provided User-Agent headers are ignored so they cannot replace the configured
identity. The selected identity is visible in Toolchain and command previews.

The installed Subfinder v2.16.0 uses its own randomized browser User-Agents for its
shared HTTP client; it has no CLI override for the dashboard's exact identity.
Individual third-party provider clients remain tool-managed, so this dashboard does
not claim to enforce every auxiliary provider request. DNS queries and direct TLS
handshakes have no User-Agent. Terminal-launched external agents manage their own
traffic; shared instructions request the configured identity for constructed HTTP calls.

## Storage and recovery

All runtime state is under `.kiroshi-data/` by default (ignored by Git):

```text
.kiroshi-data/
  kiroshi.sqlite3             # engagements, job metadata, cached assets, triage
  secrets/                 # private saved session values
  jobs/<job-id>/output.log # persistent capped evidence, one log per run
  engagements/<id>/        # agent-ready workspace and original scaffold brief
```

Back up the directory while the server is stopped. It includes sensitive evidence
and credentials. UI edits to scope preserve existing handoff/coverage files. Scope
cannot be changed while that engagement has queued or running jobs.

## Validation

```bash
python3 -m unittest discover -s tests -v
node --check dashboard/static/app.js
# Optional: actual HTTP tool binaries against a temporary loopback-only fixture.
python3 -u -m tests.integration_local
python3 -u -m tests.redirect_check
python3 -u -m tests.integration_traffic
# Optional: installed Chrome, native DevTools pipe, temporary workspace only.
node tests/browser_check.mjs
```

The integration suites open local sockets and test anonymous/session runs, retained
cache, request-token protection, Host validation, and cross-host redirect rejection.
The Chrome smoke test checks engagement/session forms, masked previews, handoff edits,
tool filtering, and mobile layout. No public targets are scanned.

## Distribution and credits

Install the published fork using [INSTALL.md](docs/INSTALL.md). The original scaffold
and methodology are by [0xcucumbersalad](https://github.com/0xcucumbersalad) in
[0xcucumbersalad/hunt](https://github.com/0xcucumbersalad/hunt); the MIT attribution
is retained. See [TRAFFIC.md](docs/TRAFFIC.md) for pacing and WAF-feedback limits.

### Run history and duplicate protection

A finished job means its process exited with code 0, not that it found a
vulnerability. The jobs table and log viewer summarize structured observations
and HTTP statuses. A 301 is a redirect response; its destination is recorded
without following it. Cloudflare/CDN metadata alone does not establish a block.

The server rejects concurrent duplicate runs for the same engagement, tool,
normalized target and session revision. Completed runs also require checking
**Repeat completed run** before another execution. A minimal hashed completion
marker survives removal of jobs/logs; cached discoveries remain available.
Changing credentials permits a new authenticated pass. Failed, cancelled or
interrupted jobs may be retried. Engagement names must be unique (ignoring case).


## Sequential engagement workflows and live execution

**Run engagement workflow** opens a preview of these ordered stages:

1. Subfinder: passive subdomain discovery.
2. dnsx: resolve scoped hosts, including eligible discoveries.
3. httpx: check scoped HTTP and HTTPS targets after host discovery.
4. tlsx: certificate/TLS inventory.
5. URLFinder: passive public URL collection.
6. httpx: check newly discovered URLs.
7. Katana: crawl responding origins.
8. httpx: check newly crawled URLs.
9. ffuf or Feroxbuster: bounded path discovery on responding origins.
10. httpx: check newly discovered paths.
11. Nuclei: the bundled server-header inventory template only.

One process runs at a time. Stage inputs are built from current scoped cache
observations after earlier jobs finish; adding a domain alone never starts work.
Wildcard base domains may seed passive Subfinder/URLFinder collection without
being authorized for active apex probes. Active targets still need explicit host
scope. Every discovered URL is filtered against current scope/exclusions.

The default limits are 50 new tool targets per stage and 200 total jobs; preview
and edit these before starting. Each job inherits the engagement's rate,
concurrency, timeout and duration ceiling. Candidate lists are capped at 2000
entries. Missing tools and limits produce **completed limited**, with skipped
stages/targets visible. Failed, blocked, timed-out or incompletely processed jobs
stop the workflow. Traffic holds continue to apply. Server restart interrupts a
workflow and never resumes network activity automatically.

Identical tool/target/session checks reuse existing completion markers and cache.
The repeat checkbox permits a fresh pass over earlier runs, while each effective
check still executes only once within the new workflow. HTTP checks after later
stages probe new URLs rather than repeatedly probing the same root. A selected
session applies only to its exact origin; other targets run anonymously. Replacing
or deleting that session stops further workflow scheduling. Scope edits require
stopping the workflow first.

Queueing an individual tool or a workflow opens its live execution view. It shows
the tool and target, stage order, lifecycle timestamps, elapsed time, log size,
exit code, observations, and full command preview. Tool diagnostics are enabled
by default in the UI, with native statistics where supported. Raw debugging
modes that print request headers are not enabled. Log output remains capped and
session values are redacted. Some tools buffer output; a quiet log is shown as
quiet rather than being presented as completed. Logs refresh every second.

**Run one tool** remains available. A fast individual httpx probe is only one
probe, not an entire engagement. Rerun retains its original tool, target, saved
identity and pacing settings rather than silently selecting httpx again.

Subfinder and URLFinder manage their own browser-style user agents for passive
source queries. Other HTTP adapters use Kiroshi's configured browser identity.
Passive provider configurations remain isolated from the user's normal home.


## Erasing history and loading feedback

In **Jobs & logs**, choose an engagement filter (or all engagements), then
**Erase jobs & logs**. The confirmation shows which scope and how many records
will be affected. Confirming removes job log directories and completed workflow
history. Engagements, sessions, findings, cached discoveries, duplicate protection,
and traffic holds remain saved. Active jobs/workflows must first finish or stop.
The UI never erases history merely from opening or cancelling the dialog.

Workflow preview and startup show animated progress messages, disable duplicate
submissions, and restore controls after errors. Reduced-motion preferences are
respected. Live workflows also show an active indicator while awaiting tool output.

Overview includes [webhook notifications](docs/NOTIFICATIONS.md) and
[performance snapshots and verification](docs/PERFORMANCE.md).
