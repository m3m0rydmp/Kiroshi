# hunt

> **WSL dashboard extension:** This branch also includes a local web engagement
> console with scope settings, WSL tool discovery/execution, cached recon,
> anonymous/session runs, live logs, findings, and Claude Code/Codex handoffs.
> Run `./hunt-dashboard`, then open `http://localhost:8741`.
> See [DASHBOARD.md](DASHBOARD.md) for setup, capabilities and current limits.

Scaffold a bug bounty agent workspace in one command. `hunt <target>` creates a
per-target folder with an `AGENT.md` brief — a ready-to-run operating manual for
an autonomous, impact-first bug bounty agent (access control, BOLA/IDOR, business
logic, and whatever else actually harms a user, tenant, or the business).

> **Authorized testing only.** This tool scaffolds a brief; it does not attack
> anything. Test only assets a bug bounty program or written authorization puts
> in scope. No authorization, no testing.

## What it does

Running `hunt <target>` will:

1. Slugify the target name (`"Acme Corp"` → `acme-corp`).
2. Create a folder `./<slug>/`.
3. Prompt (on a TTY) for the program URL/policy, in-scope domains, and
   out-of-scope domains.
4. Write `./<slug>/AGENT.md` — the full agent brief with your scope filled in.

The brief covers scope gating, test-account setup, tooling (Burp MCP proxy +
HTTP Workbench MCP), asset/feature discovery, the BOLA/BAC/business-logic/
client-side methodology, the escalation ladder, evidence/reporting format,
cleanup/revert discipline, and a self-driving working loop.

## Install

```bash
# clone
git clone https://github.com/0xcucumbersalad/hunt.git
cd hunt

# put it on your PATH
install -m 0755 hunt ~/.local/bin/hunt      # or: cp hunt ~/.local/bin && chmod +x ~/.local/bin/hunt

# verify
hunt --help
```

Make sure `~/.local/bin` is on your `PATH`:

```bash
export PATH="$HOME/.local/bin:$PATH"   # add to ~/.zshrc or ~/.bashrc
```

Requires `bash`. Uses only standard POSIX tools (`sed`, `tr`, `date`).

## Usage

```
usage: hunt <target> [--force]
  <target>   program/target name (e.g. google, "acme corp")
  --force    overwrite existing AGENT.md
```

### Examples

```bash
# interactive — prompts for scope
hunt acme

# multi-word target (quote it)
hunt "Acme Corp"

# overwrite an existing brief
hunt acme --force

# non-interactive (no TTY) — scope left as "_(fill in)_" placeholders
hunt acme < /dev/null
```

When run with a terminal attached, `hunt` asks three questions:

```
Program URL / policy: https://hackerone.com/acme
In-scope domains (comma-sep): *.acme.com, api.acme.io
Out-of-scope (comma-sep): blog.acme.com, status.acme.com
```

Anything left blank becomes a `_(fill in)_` placeholder you edit later.

### Output

```
hunt: created ./acme/AGENT.md
next: cd acme && open AGENT.md
```

```
acme/
└── AGENT.md
```

As the agent works, it maintains state files alongside `AGENT.md` in the same
folder:

| File             | Purpose                                            |
|------------------|----------------------------------------------------|
| `scope-hosts.md` | Breadth queue — each host `untested → tested`       |
| `features.md`    | Depth queue per host — each feature `untested → tested` |
| `todo.md`        | Live endpoints and hypotheses to chase next        |
| `accounts.md`    | Test identities: email, role, tenant, IDs, tokens  |
| `cleanup.md`     | Every write made + its undo action (revert log)    |

## The brief in short

- **Impact-only.** No info leaks, header nits, self-XSS, or theoretical issues.
- **Escalate every hit.** A raw IDOR is a lead; chain it to maximum proven impact.
- **Two identities minimum** where obtainable — prove a crossed boundary.
- **Everything routes through the Burp MCP proxy.** A request not in Burp didn't happen.
- **Cleanup is mandatory.** Every write logged and reverted; leave no trace.
- **Self-driving loop.** The agent picks the next action from on-disk state and
  keeps going until every host and feature is tested and every finding escalated.

## License

MIT
