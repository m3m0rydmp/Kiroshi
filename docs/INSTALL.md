# Installing Hunt

## Platform and prerequisites

Use a native Linux distribution or a Linux distribution inside WSL2. Native Windows
and macOS launchers are not supported. The Windows browser can connect to the WSL
service through localhost forwarding. No Docker container is needed: the native
runner intentionally uses the Linux tools installed on that machine.

Required: Python 3.10 or newer, Bash, GNU coreutils (`readlink`, `date`, `tr`), `sed`
and Git for clone/update. On Debian/Ubuntu-based systems, if these are missing:

```bash
sudo apt update
sudo apt install python3 git bash coreutils sed ca-certificates
```

The dashboard has no pip or npm runtime dependencies. Go/Rust are only needed when
you choose to compile scan tools; official prebuilt releases are another option.
Chrome is optional for browser QA, not required for the built-in non-headless crawl.
Claude Code/Codex and their provider credentials are separate optional installations.

## Clone the published fork

```bash
git clone https://github.com/m3m0rydmp/hunt.git
cd hunt
bash install.sh
./hunt-dashboard
```

The URL assumes the fork is published as `m3m0rydmp/hunt`. Change it if renamed.
If the dashboard is only on `dashboard-wsl`, add `--branch dashboard-wsl` to clone.
The `install.sh` script never downloads tools, runs sudo, starts a background service,
or makes target requests. It checks Python, creates a symlink launcher, and runs the
local tool doctor. Help/compatibility checks execute installed tools with `-h`/`--help`.

An existing unrelated launcher is never overwritten. Options:

```bash
bash install.sh --check-only
bash install.sh --bin-dir "$HOME/bin"
```

To use `hunt-dashboard` from any directory, add the chosen launcher directory to PATH.
For the default directory:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Add that line to your own `~/.bashrc` or `~/.zshrc` if desired. Keep the checkout in
place: the launcher points to it. Moving it requires removing/reviewing the old
symlink and running the installer from the new location.

## Open and restart

Open **http://localhost:8741** in your browser. Keep the WSL/Linux terminal open.
Ctrl+C stops the server. After reboot, open the Linux terminal and run:

```bash
hunt-dashboard
```

Or `cd` to the checkout and run `./hunt-dashboard` if PATH was not configured.
No automatic boot service is installed. A different port/data location is optional:

```bash
./hunt-dashboard --port 8742 --data-dir "$HOME/.local/share/hunt-dashboard"
```

Changing data directories opens a different workspace; it does not migrate existing
data. Do not run two server processes against the same data directory. If localhost
does not forward from Windows, check WSL localhost forwarding instead of exposing
the dashboard on a public interface. An occupied port usually means another server
is already running; stop that server or select another port.

## Install optional scan tools

Only install tools you intend to use. Missing tools do not prevent startup. Get
releases/packages from each tool's maintainer, then run the doctor again.

| Adapter | Official installation source |
|---|---|
| Subfinder | [ProjectDiscovery install guide](https://docs.projectdiscovery.io/opensource/subfinder/install) |
| dnsx | [ProjectDiscovery install guide](https://docs.projectdiscovery.io/opensource/dnsx/install) |
| httpx | [ProjectDiscovery install guide](https://docs.projectdiscovery.io/opensource/httpx/install) |
| tlsx | [Maintainer repository](https://github.com/projectdiscovery/tlsx#installation) |
| Katana | [ProjectDiscovery install guide](https://docs.projectdiscovery.io/opensource/katana/install) |
| Nuclei | [ProjectDiscovery install guide](https://docs.projectdiscovery.io/opensource/nuclei/install) |
| Feroxbuster | [Maintainer repository](https://github.com/epi052/feroxbuster#installation) |
| ffuf | [Maintainer repository](https://github.com/ffuf/ffuf#installation) |

For a supported, current Go toolchain, the maintainer installation commands are:

```bash
go install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
go install github.com/projectdiscovery/dnsx/cmd/dnsx@latest
go install github.com/projectdiscovery/httpx/cmd/httpx@latest
go install github.com/projectdiscovery/tlsx/cmd/tlsx@latest
go install github.com/projectdiscovery/katana/cmd/katana@latest
go install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest
go install github.com/ffuf/ffuf/v2@latest
```

These commands download/build third-party software; the installer does not run them.
Check the linked maintainer requirements first. Prefer pinned release versions when
you need reproducible tooling; `@latest` can change adapter compatibility. Install
Feroxbuster through its documented release/package options or Rust instructions.
Do not use `pip install httpx` as a replacement for ProjectDiscovery's executable.

## Tool detection and paths

Detection runs on the local machine. It looks for executables in standard per-user
directories (`~/.pdtm/go/bin`, `~/go/bin`, `~/.cargo/bin`, `~/.local/bin`), configured
`GOBIN`/`GOPATH/bin`, and PATH. A valid explicit override has priority. Stale overrides
are shown with a warning and fall back to autodetection. Displayed paths are ordinary
diagnostic information; new users do not need the original developer's home directory.

**Toolchain → Path** sets an absolute executable override for that tool only. Leave
it empty and save to return to autodetection. Saving one override does not freeze
other detected tools. Overrides live in the local SQLite state, never in a tracked
machine-wide configuration. Old installations affected by the earlier path-saving
behavior can clear each unwanted override with an empty value.

**Toolchain → Check binaries** checks expected adapter help flags. In the terminal:

```bash
python3 -m dashboard.doctor
python3 -m dashboard.doctor --json
python3 -m dashboard.doctor --require-tools
python3 -m dashboard.doctor --data-dir "$HOME/.local/share/hunt-dashboard"
```

`--require-tools` exits nonzero if any of the eight scan adapters is missing or
incompatible. Normal checks allow missing optional tools. JSON output includes local
paths; review it before sharing. The checks verify expected flags, not every possible
behavior/version combination. Upgrade or choose the correct binary when flagged
incompatible. ProjectDiscovery httpx is distinguished by its help signature; an
unrelated Python CLI is not selected automatically.

Inventory-only tools may be detected but cannot be queued until they have a supported
adapter. A binary appearing in the catalog is not a claim of execution support.
Your tool configurations are isolated per job; external provider keys, proxy settings
and templates are not implicitly inherited. Subfinder's existing provider-key file is
not loaded by this version. No program-specific tool installation is downloaded on demand.

## Update and back up

Stop the server before updating or backing up. From the checkout, on the branch you
installed:

```bash
git pull --ff-only
bash install.sh --check-only
./hunt-dashboard
```

Back up the selected data directory separately. `.hunt-data/` contains credentials,
machine-local paths and evidence and is ignored by Git; do not publish it. Put any
custom data directory outside the checkout. Tool versions and absolute paths in
old job records are historical evidence, not portable installation settings.

For the original scaffold-only CLI, see [SCAFFOLD.md](SCAFFOLD.md).
