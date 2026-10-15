# Kiroshi — local bug bounty dashboard

A browser-based engagement workspace that runs installed Linux/WSL tools, keeps
recon and evidence locally, and prepares shared workspaces for Claude Code or Codex.
The interface uses a cyan/lavender/sunset theme.

## Install and start

Requires **Linux or WSL2, Python 3.10+, Bash and GNU coreutils**. Git is needed to
clone/update. No npm build, pip packages, Docker, model key or paid service is needed
for the dashboard itself. Install scan tools separately as needed.

```bash
git clone https://github.com/m3m0rydmp/Kiroshi.git
cd Kiroshi
bash install.sh
./kiroshi
```

Open **http://localhost:8741**. Keep the terminal open; Ctrl+C stops the server.
If this dashboard is published on a non-default branch, clone that branch instead:
`git clone --branch dashboard-wsl https://github.com/m3m0rydmp/Kiroshi.git`.
Adjust the repository URL if the published fork is renamed.

The installer creates a local launcher in `~/.local/bin` and checks tools. It does
not install scan tools, use sudo, change your shell files, start a service, or run
scans. The dashboard starts even when every optional tool is missing.

**[Installation and tool setup](docs/INSTALL.md)** ·
**[Traffic controls and WAF limits](docs/TRAFFIC.md)** ·
**[Detailed usage](DASHBOARD.md)** · **[Original scaffold CLI](docs/SCAFFOLD.md)**

## Features

- Engagement scope, exclusions, rate ceilings and bounded job execution.
- Automatic machine-local tool discovery, explicit path overrides and compatibility checks.
- Nine scan adapters: Subfinder, dnsx, httpx, tlsx, URLFinder, Katana, Feroxbuster, ffuf and Nuclei.
- A broader 36-tool inventory; inventory-only entries do not imply runnable support.
- Previewable sequential engagement workflows, with HTTP checks after each discovery stage.
- Anonymous recon cache, named cookie/header sessions, live activity, tool diagnostics and result downloads.
- Gentle pacing, tool-supported delay/jitter and observed block-response cooldowns.
- Evidence-readiness checks before confirmed/reported status and public disclosure references.
- Shared instructions and handoff files for terminal-based Claude Code/Codex sessions.

Nuclei currently runs a bundled inventory template, not a general vulnerability scan.
Agent execution stays in your terminal. The dashboard does not submit reports to
HackerOne or automatically exploit findings.

## First engagement

1. Create an engagement with its policy URL and explicitly authorized hosts/exclusions.
2. Check **Toolchain**; install any tools you need and use **Check binaries**.
3. Choose **Run engagement workflow**, preview the ordered stages, then start and watch live output. Use **Run one tool** for an individual check. Results persist in **Asset cache** and **Jobs & logs**.
4. Add an exact-origin cookie/header session when ready; run again against cached assets.
5. Review candidates in **Findings** and use **Public reports** for attributed historical context.
6. Save **Agent handoff**, then copy the terminal command for your configured agent client.

Paths shown in Toolchain describe **the current installation**, not paths someone
else needs to recreate. Overrides live in ignored local state. Missing/stale paths
fall back to autodetection; the detector distinguishes ProjectDiscovery httpx from
the unrelated Python HTTP client CLI.

## Traffic behavior

The default ceiling is 5 requests/second with one worker per tool. Runs can choose
a gentle 1 request/second profile or a lower rate within the engagement ceiling.
Where emitted scanner output exposes configured 429/503 signals, the runner can
stop the job and hold queued runs to that origin. HTTP 403 is optional because it
can represent expected access control. See the [support matrix](docs/TRAFFIC.md).

These are pacing and feedback controls, not guaranteed WAF evasion. There is no
automatic challenge solving, payload obfuscation, IP rotation or authentication
bypass. Real browser User-Agent headers do not reproduce a browser's full behavior
or TLS fingerprint. A blocked run needs review; it is not proof of a vulnerability.

## Local data

The server binds only to `127.0.0.1`. Runtime state defaults to `.kiroshi-data/`, ignored
by Git. It includes credentials and sensitive evidence; keep it private and back it
up while the server is stopped. Optional custom data directories should live outside
the checkout. This is a single-user service without remote login or multi-user isolation.

## Validation

```bash
python3 -m dashboard.doctor
python3 -m unittest discover -s tests -v
```

Optional local HTTP/browser integration checks are documented in [DASHBOARD.md](DASHBOARD.md).

## Credits and license

The original `hunt` scaffold script and methodology were created by
[0xcucumbersalad](https://github.com/0xcucumbersalad) in
[0xcucumbersalad/hunt](https://github.com/0xcucumbersalad/hunt).
This project extends that script with the local dashboard and runner. Original
attribution is retained in [LICENSE](LICENSE). MIT licensed.
