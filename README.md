# Kiroshi

**A local dashboard for bug bounty engagements, built around your Linux tools.**

[![License: MIT](https://img.shields.io/badge/License-MIT-a9eaf4)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-c8b0f0)](docs/INSTALL.md)
[![Linux / WSL2](https://img.shields.io/badge/Platform-Linux%20%2F%20WSL2-ffb8aa)](docs/INSTALL.md)

Kiroshi brings scope management, sequential recon workflows, cached discoveries,
authenticated sessions, live logs, and evidence review into one browser interface.
Commands run through your installed Linux/WSL binaries. Claude Code and Codex are
optional tools for deeper analysis; the dashboard and scanning workflows run
without an AI provider.

[Quick start](#quick-start) · [Tools and workflow](#tools-and-workflow) ·
[Documentation](#documentation) · [Credits](#credits-and-license)

## Quick start

**Requirements:** Linux or WSL2, Python 3.10+, Bash, GNU coreutils, `sed`, and Git.
The dashboard has no pip or npm runtime dependencies and does not require Docker.

```bash
git clone https://github.com/m3m0rydmp/Kiroshi.git
cd Kiroshi
bash install.sh
./kiroshi
```

Open **[http://localhost:8741](http://localhost:8741)**. Keep the terminal open;
press **Ctrl+C** to stop the server. After reboot, open your Linux terminal and run
`./kiroshi` from the checkout again.

The installer creates a launcher in `~/.local/bin` and checks available tools. It
does not run scans, download scanner binaries, change shell startup files, or
install a boot service. Missing tools do not prevent the dashboard from starting.

### Set up workflow tools

```bash
./kiroshi install-tools --dry-run   # Show missing tools and installation commands
./kiroshi install-tools             # Install missing workflow tools
./kiroshi doctor --require-tools    # Check executable and adapter compatibility
```

The explicit tool installer uses Go for the supported Go tools and Cargo for
Feroxbuster. Install the required compilers first, or use the maintainers' prebuilt
releases. Existing binaries are not automatically upgraded or overwritten.
See [installation and tool setup](docs/INSTALL.md) for prerequisites and alternatives.

## First engagement

1. **Define scope.** Create an engagement with authorized assets, exclusions,
   the program policy, request-rate limits, and job time limits.
2. **Check the toolchain.** Review detected executables and run **Check binaries**.
   Paths are detected on the current machine; saved overrides are local settings.
3. **Preview the workflow.** Select **Run engagement workflow**, review its ordered
   stages and limits, then choose **Start workflow & watch live**. Use **Run one
   tool** for an individual check.
4. **Review discoveries.** Results persist in **Asset cache** and **Jobs & logs**.
   Add an exact-origin cookie/header session when an authenticated pass is needed.
5. **Verify candidates.** Record reproducible evidence in **Findings**. Public
   reports provide historical context, never proof of eligibility or impact.
6. **Continue with an agent if useful.** **Agent handoff** prepares shared scope,
   evidence, and notes for terminal-based Claude Code or Codex sessions.

Only test assets for which you have authorization, within the program's rules.

## Tools and workflow

Kiroshi has **nine runnable adapters** and a **36-tool inventory**. Installing a
catalog entry does not automatically make it executable or add it to a workflow.
Tools such as `anew`, `uro`, Amass, Nmap, Dalfox, and sqlmap remain inventory-only.
Kiroshi already deduplicates cached assets and identical tool runs internally.

The engagement workflow runs one process at a time:

| Stage | Tool                | Purpose                                            |
| ----- | ------------------- | -------------------------------------------------- |
| 1     | Subfinder           | Discover candidate subdomains from passive sources |
| 2     | dnsx                | Resolve authorized hosts                           |
| 3     | httpx               | Check HTTP/HTTPS services after host discovery     |
| 4     | tlsx                | Collect certificate and TLS inventory              |
| 5     | URLFinder           | Collect URLs from public sources                   |
| 6     | httpx               | Check newly discovered URLs                        |
| 7     | Katana              | Crawl responding origins                           |
| 8     | httpx               | Check newly crawled URLs                           |
| 9     | ffuf or Feroxbuster | Discover paths using the bundled wordlist          |
| 10    | httpx               | Check newly discovered paths                       |
| 11    | Nuclei              | Run the bundled server-header inventory template   |

Later stages use scoped discoveries from earlier stages. Identical completed
checks reuse cached results unless an explicit repeat is requested; the same
effective check runs at most once within a workflow.

Default workflow bounds are **50 new targets per stage** and **200 total tool
jobs**, configurable before starting. Missing tools and reached limits are shown
as limited coverage. Failed or blocked jobs stop the workflow. A restart interrupts
it rather than automatically resuming network activity.

**Nuclei currently performs inventory only.** Kiroshi does not automatically run
broad vulnerability templates, exploit findings, or submit reports to HackerOne.

## Workspace features

| Area               | Capabilities                                                                                                     |
| ------------------ | ---------------------------------------------------------------------------------------------------------------- |
| Scope and sessions | Host/IP and wildcard rules, URL boundaries, exclusions, exact-origin private cookies and headers                 |
| Execution          | Workflow previews, duplicate protection, bounded jobs, cancellation, loading indicators and stage progress       |
| Evidence           | Persistent asset cache, live tool output, lifecycle events, command previews and log downloads                   |
| Review             | Evidence-completeness checks, reviewer attestations and attributed public-report references                      |
| Notifications      | Discord embeds, Telegram messages, Slack blocks and generic JSON webhooks, with event settings and test delivery |
| Performance        | Backend memory/CPU snapshots, sampled scanner resource usage and a repeatable local benchmark                    |
| History            | Confirmed job/log erasure that preserves engagements, discoveries, findings and duplicate protection             |

### Traffic and scope boundaries

The default rate ceiling is **5 requests/second**, with one worker per tool.
Supported adapters offer lower rates, gentle pacing, delays, or jitter. Observable
429/503 signals can stop a job and hold subsequent runs to that origin; 403
monitoring is optional. Tool output determines which signals are visible.

These controls do not guarantee WAF evasion or reproduce a browser's TLS and
JavaScript behavior. URL-only rules can be saved, but current scan adapters require
whole-host scope and refuse hosts with URL exclusions. See the
[traffic support matrix](docs/TRAFFIC.md) and [usage guide](DASHBOARD.md).

### Local data and secrets

The server binds to **127.0.0.1** and is intended for one local user. Runtime data
defaults to `.kiroshi-data/`, which Git ignores. Earlier installations can continue
using their existing data directory. It contains sensitive evidence and private
session/webhook settings; back it up while the server is stopped.

Saved credentials and webhook URLs are not returned through the API. Notifications
exclude session credentials and raw scan logs. There is no remote login or
multi-user isolation. Custom data directories should live outside the checkout.

## Documentation

| Guide                                         | Contents                                                                 |
| --------------------------------------------- | ------------------------------------------------------------------------ |
| [Installation](docs/INSTALL.md)               | WSL/Linux setup, missing-tool installation, detection and path overrides |
| [Dashboard usage](DASHBOARD.md)               | Engagements, workflows, sessions, findings and agent handoffs            |
| [Traffic controls](docs/TRAFFIC.md)           | Rate limits, cooldowns and adapter-specific support                      |
| [Notifications](docs/NOTIFICATIONS.md)        | Webhook formats, Telegram chat IDs, event settings and secret storage    |
| [Performance](docs/PERFORMANCE.md)            | Resource metrics, benchmark procedure and measured results               |
| [Business logic review](docs/LOGIC_REVIEW.md) | Reviewed workflows, corrected issues and remaining boundaries            |
| [Scaffold CLI](docs/SCAFFOLD.md)              | The retained upstream script and its commands                            |

## Verification

```bash
./kiroshi doctor --require-tools
python3 -m unittest discover -s tests -v
node tests/browser_check.mjs
python3 -m tests.performance_check --output /tmp/kiroshi-performance.json
```

Browser checks require Node.js and a compatible Chrome installation; neither is
needed to use the dashboard. Browser and performance fixtures use temporary local
data. Additional loopback integration checks are documented in [DASHBOARD.md](DASHBOARD.md).

## Credits and license

Kiroshi extends the `hunt` scaffold script and methodology created by
[0xcucumbersalad](https://github.com/0xcucumbersalad) in
[0xcucumbersalad/hunt](https://github.com/0xcucumbersalad/hunt).
The upstream script and attribution are retained.

Released under the [MIT License](LICENSE).
