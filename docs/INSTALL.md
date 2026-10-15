# Installing Kiroshi

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

## Clone the repository

```bash
git clone https://github.com/m3m0rydmp/Kiroshi.git
cd Kiroshi
bash install.sh
./kiroshi
```

The `install.sh` script never downloads tools, runs sudo, starts a background service,
or makes target requests. It checks Python, creates a symlink launcher, and runs the
local tool doctor. Help/compatibility checks execute installed tools with `-h`/`--help`.

An existing unrelated launcher is never overwritten. Options:

```bash
bash install.sh --check-only
bash install.sh --bin-dir "$HOME/bin"
```

To use `kiroshi` from any directory, add the chosen launcher directory to PATH.
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
kiroshi
```

Or `cd` to the checkout and run `./kiroshi` if PATH was not configured.
No automatic boot service is installed. A different port/data location is optional:

```bash
./kiroshi --port 8742 --data-dir "$HOME/.local/share/kiroshi"
```

Changing data directories opens a different workspace; it does not migrate existing
data. Do not run two server processes against the same data directory. If localhost
does not forward from Windows, check WSL localhost forwarding instead of exposing
the dashboard on a public interface. An occupied port usually means another server
is already running; stop that server or select another port.

## Install optional scan tools

Only install tools you intend to use. Missing tools do not prevent startup. Get
releases/packages from each tool's maintainer, then run the doctor again.

| Adapter     | Official installation source                                                                    |
| ----------- | ----------------------------------------------------------------------------------------------- |
| URLFinder   | [ProjectDiscovery repository](https://github.com/projectdiscovery/urlfinder)                    |
| Subfinder   | [ProjectDiscovery install guide](https://docs.projectdiscovery.io/opensource/subfinder/install) |
| dnsx        | [ProjectDiscovery install guide](https://docs.projectdiscovery.io/opensource/dnsx/install)      |
| httpx       | [ProjectDiscovery install guide](https://docs.projectdiscovery.io/opensource/httpx/install)     |
| tlsx        | [Maintainer repository](https://github.com/projectdiscovery/tlsx#installation)                  |
| Katana      | [ProjectDiscovery install guide](https://docs.projectdiscovery.io/opensource/katana/install)    |
| Nuclei      | [ProjectDiscovery install guide](https://docs.projectdiscovery.io/opensource/nuclei/install)    |
| Feroxbuster | [Maintainer repository](https://github.com/epi052/feroxbuster#installation)                     |
| ffuf        | [Maintainer repository](https://github.com/ffuf/ffuf#installation)                              |

For a supported, current Go toolchain, the maintainer installation commands are:

```bash
go install github.com/projectdiscovery/urlfinder/cmd/urlfinder@latest
go install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
go install github.com/projectdiscovery/dnsx/cmd/dnsx@latest
go install github.com/projectdiscovery/httpx/cmd/httpx@latest
go install github.com/projectdiscovery/tlsx/cmd/tlsx@latest
go install github.com/projectdiscovery/katana/cmd/katana@latest
go install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest
go install github.com/ffuf/ffuf/v2@latest
```

These commands download/build third-party software. The launcher installer does not
run them; the explicit `kiroshi install-tools` command installs missing tools.
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
python3 -m dashboard.doctor --data-dir "$HOME/.local/share/kiroshi"
```

`--require-tools` exits nonzero if any of the nine scan adapters is missing or
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
./kiroshi
```

Back up the selected data directory separately. `.kiroshi-data/` contains credentials,
machine-local paths and evidence and is ignored by Git; do not publish it. Put any
custom data directory outside the checkout. Tool versions and absolute paths in
old job records are historical evidence, not portable installation settings.

For the original scaffold-only CLI, see [SCAFFOLD.md](SCAFFOLD.md).

## Existing local installations

The canonical launcher is `kiroshi`; the earlier `hunt-dashboard` launcher remains
a compatibility entry point. Existing `.hunt-data/` directories and `hunt.sqlite3`
databases are opened in place when the new names do not already exist, preserving
stored paths and evidence. New installations use `.kiroshi-data/kiroshi.sqlite3`.
Runtime directories for both layouts are ignored by Git. No data is copied or
deleted automatically. If both directories exist, select the intended one explicitly
with `--data-dir`; the new default directory takes precedence.

Configuration now uses `KIROSHI_USER_AGENT`, `KIROSHI_H1_API_USERNAME` and
`KIROSHI_H1_API_TOKEN`. Earlier `HUNT_` environment names remain supported as
fallbacks, with canonical names taking precedence. Rerun `bash install.sh` to add
the canonical launcher to this machine.

## Install missing workflow tools

```bash
./kiroshi install-tools --dry-run
./kiroshi install-tools
./kiroshi doctor --require-tools
```

The explicit tool setup command installs only missing workflow adapters into
`~/.local/bin`, using fixed upstream Go module paths and Cargo for Feroxbuster.
Existing installed binaries are skipped, not upgraded; incompatible overrides
require manual review. It refuses to overwrite a file at the destination. A current
Go toolchain is required for Go builds and Rust/Cargo for Feroxbuster. Missing
compilers or build dependencies produce a terminal error with the upstream output.
The helper never runs sudo or edits shell startup files. `install.sh` remains the
launcher installer; tool downloads happen only with `kiroshi install-tools`.
