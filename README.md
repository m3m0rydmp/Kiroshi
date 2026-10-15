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
[Wiki](https://github.com/m3m0rydmp/Kiroshi/wiki) · [Credits](#credits-and-license)

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
   Search and filter the paginated cache by host, type, source or HTTP status.
   Add an exact-origin cookie/header session when an authenticated pass is needed.
5. **Verify candidates.** Record reproducible evidence in **Findings**. Public
   reports provide historical context, never proof of eligibility or impact.
6. **Continue with an agent if useful.** **Agent handoff** prepares cached engagement
   data for review,
   then runs Claude / your configured provider or Codex analysis in the dashboard.
   Terminal launch commands and shared notes remain available.

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

New workflows default to **unlimited total tool jobs** (blank or `0` in the optional
total-job limit). Enter a positive number to set a cap. Per-stage target limits are
also optional and unlimited by default. All eligible candidates remain in a SQLite
work queue, without a fixed candidate cutoff. There is no overall workflow timer.
Individual tool timeouts still apply. Missing tools and reached limits are shown
as limited coverage. Failed or blocked jobs stop the workflow. A restart interrupts
it rather than automatically resuming network activity.

**Nuclei currently performs inventory only.** Kiroshi does not automatically run
broad vulnerability templates, exploit findings, or submit reports to HackerOne.

## Workspace features

| Area               | Capabilities                                                                                                     |
| ------------------ | ---------------------------------------------------------------------------------------------------------------- |
| Scope and sessions | Host/IP and wildcard rules, URL boundaries, exclusions, exact-origin private cookies and headers                 |
| Execution          | Ordered workflows, optional limits, checkpoint resume, duplicate protection and live progress                    |
| Evidence           | Paginated asset search, host grouping, lazy evidence, live tool output and log downloads                         |
| Agent analysis     | Engagement-specific context, Claude/provider or Codex web analysis, cancellation and saved results               |
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

Read the **[GitHub Wiki](https://github.com/m3m0rydmp/Kiroshi/wiki)** for installation,
usage and troubleshooting. Versioned copies remain available below for offline use
and reviewing documentation changes alongside code.

| Guide                                       | Wiki                                                                                     | Versioned source                          |
| ------------------------------------------- | ---------------------------------------------------------------------------------------- | ----------------------------------------- |
| Installation and tool detection             | [Installation](https://github.com/m3m0rydmp/Kiroshi/wiki/Installation)                   | [INSTALL.md](docs/INSTALL.md)             |
| Workflows, asset cache and agent analysis   | [Dashboard](https://github.com/m3m0rydmp/Kiroshi/wiki/Dashboard)                         | [DASHBOARD.md](DASHBOARD.md)              |
| Traffic controls and WAF feedback           | [Traffic controls](https://github.com/m3m0rydmp/Kiroshi/wiki/Traffic-controls)           | [TRAFFIC.md](docs/TRAFFIC.md)             |
| Webhook setup and test notifications        | [Notifications](https://github.com/m3m0rydmp/Kiroshi/wiki/Notifications)                 | [NOTIFICATIONS.md](docs/NOTIFICATIONS.md) |
| Resource metrics and benchmarks             | [Performance](https://github.com/m3m0rydmp/Kiroshi/wiki/Performance)                     | [PERFORMANCE.md](docs/PERFORMANCE.md)     |
| Corrected behavior and remaining boundaries | [Business logic review](https://github.com/m3m0rydmp/Kiroshi/wiki/Business-logic-review) | [LOGIC_REVIEW.md](docs/LOGIC_REVIEW.md)   |
| Original scaffold CLI                       | [Scaffold CLI](https://github.com/m3m0rydmp/Kiroshi/wiki/Scaffold-CLI)                   | [SCAFFOLD.md](docs/SCAFFOLD.md)           |

Verification commands and fixture requirements are in the usage and performance
guides. Maintainers can regenerate the Wiki using [the publishing guide](docs/WIKI.md).

## Credits and license

Kiroshi extends the `hunt` scaffold script and methodology created by
[0xcucumbersalad](https://github.com/0xcucumbersalad) in
[0xcucumbersalad/hunt](https://github.com/0xcucumbersalad/hunt).
The upstream script and attribution are retained.

Released under the [MIT License](LICENSE).
