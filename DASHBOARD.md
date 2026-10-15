# Hunt dashboard — Afterglow

A local WSL engagement console built on [0xcucumbersalad/hunt](https://github.com/0xcucumbersalad/hunt).
The original `hunt` CLI is retained. The dashboard invokes that actual script for
each engagement, keeps its brief as a methodology reference, and supplies bounded
shared instructions for Claude Code and Codex.

The interface uses moonlight cyan, lavender, violet, and peach/coral sunset colors.
There are no remote fonts, analytics, CDNs, or image dependencies.

## Start in WSL

Requires Python 3.10+ and Bash. No Python packages, Node build, Docker, or model API
keys are required to run the dashboard itself.

```bash
cd ~/AI/hunt-dashboard
./hunt-dashboard
```

Open **http://localhost:8741** from your Windows browser. If WSL localhost forwarding
is disabled, enable that forwarding; do not expose this service on a public interface.
The process binds to IPv4 loopback only. Stop it with Ctrl+C.

```bash
./hunt-dashboard --port 8742 --data-dir ~/.local/share/hunt-dashboard
```

## Engagement workflow

1. Create an engagement. Enter the program policy URL separately from explicit
   in-scope hostnames/IPs and excluded hosts. `*.example.com` covers subdomains,
   not the apex. URL/path, port-specific, CIDR, and mobile-app scope rules are not
   represented by this first version; do not use a broader hostname rule to stand
   in for a narrower program authorization.
2. Choose a ready tool, enter an authorized target, preview, then queue an anonymous
   run. Nothing runs just because you entered a domain or created an engagement.
3. Results remain in the local cache and per-run logs across browser/server restarts.
   The normalized cache includes supported JSON URL/host observations and scoped
   Subfinder names. All runs retain capped text logs even when normalization finds
   no assets. Excluded discoveries are not promoted into the asset cache.
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

Eight adapters:

| Tool | Initial runnable profile |
|---|---|
| Subfinder | Passive discovery for a selected in-scope seed hostname |
| dnsx | A / AAAA / CNAME inventory |
| httpx | Selected-scheme status/title/technology inventory, no redirects |
| tlsx | Certificate / TLS inventory on selected port or 443 |
| Katana | Non-headless, depth-two crawl confined to the selected origin |
| Feroxbuster | Non-recursive GET discovery, small bundled wordlist |
| ffuf | GET path discovery, small bundled wordlist |
| Nuclei | Bundled server-header inventory template only |

Other entries are **inventory-only**, including Amass, Findomain, assetfinder, Chaos,
URLFinder, gau, waybackurls, puredns, shuffledns, dnsgen, alterx, Naabu, Nmap, Arjun,
ParamSpider, Dalfox, sqlmap, crlfuzz, Interactsh, Gitleaks, TruffleHog, jq, anew, uro,
unfurl, Notify, Claude Code, and Codex. They need a reviewed adapter before dashboard
execution. There is no arbitrary shell-command input.

Add executable metadata and a bounded argv builder in `dashboard/tools.py`, then
exercise it against a local fixture. Add a normalizer where useful. Confirm flags
against the installed tool version. Authenticated adapters also need private-file
header support and exact-origin behavior; never persist credentials in the job argv.

Subfinder uses an isolated home, so your existing provider API-key config is not
loaded in this version. Broad Nuclei template selection, custom wordlists, port-scan
execution, archive import, and multi-stage automated pipelines are not implemented.
The dashboard does not currently configure Burp MCP or HTTP Workbench MCP.

## Sessions and local security

Session values are stored in plaintext JSON files under `.hunt-data/secrets/` with
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

## Storage and recovery

All runtime state is under `.hunt-data/` by default (ignored by Git):

```text
.hunt-data/
  hunt.sqlite3             # engagements, job metadata, cached assets, triage
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
# Optional: installed Chrome, native DevTools pipe, temporary workspace only.
node tests/browser_check.mjs
```

The integration suites open local sockets and test anonymous/session runs, retained
cache, request-token protection, Host validation, and cross-host redirect rejection.
The Chrome smoke test checks engagement/session forms, masked previews, handoff edits,
tool filtering, and mobile layout. No public targets are scanned.

## GitHub fork

This checkout has branch `dashboard-wsl`. To create your actual GitHub fork after
authenticating GitHub CLI:

```bash
gh auth login
gh repo fork 0xcucumbersalad/hunt --clone=false
git remote rename origin upstream
git remote add origin https://github.com/m3m0rydmp/hunt.git
git add .
git commit -m "Add local WSL engagement dashboard"
git push -u origin dashboard-wsl
```

No GitHub fork is implied by creating a local branch. Keep upstream attribution
and the original MIT license.
