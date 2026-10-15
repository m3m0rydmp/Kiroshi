"""Explicit terminal-only installation of missing workflow binaries."""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import shlex
import shutil
import sqlite3
import subprocess

from .config import database_path, default_data_dir
from .tools import discover, probe


MODULES = {
    "subfinder": "github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest",
    "dnsx": "github.com/projectdiscovery/dnsx/cmd/dnsx@latest",
    "httpx": "github.com/projectdiscovery/httpx/cmd/httpx@latest",
    "tlsx": "github.com/projectdiscovery/tlsx/cmd/tlsx@latest",
    "katana": "github.com/projectdiscovery/katana/cmd/katana@latest",
    "urlfinder": "github.com/projectdiscovery/urlfinder/cmd/urlfinder@latest",
    "nuclei": "github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest",
    "ffuf": "github.com/ffuf/ffuf/v2@latest",
}


def install_missing(tools, dry_run=False):
    missing = [t for t in tools if t["adapter"] and not t["installed"]]
    incompatible = [t for t in tools if t["adapter"] and t["installed"] and not t["runnable"]]
    if incompatible:
        print("Existing incompatible binaries require manual review: " + ", ".join(t["name"] for t in incompatible))
        return 1
    if not missing:
        print(f"All {sum(t['adapter'] for t in tools)} workflow tools are installed and compatible. Nothing to install.")
        return 0
    destination = Path.home() / ".local" / "bin"
    plan = []
    for tool in missing:
        name = tool["name"]
        executable = destination / name
        if executable.exists() or executable.is_symlink():
            print(f"Refusing to overwrite an existing file: {executable}. Review it before retrying.")
            return 1
        if name in MODULES:
            builder = shutil.which("go")
            args = [builder or "go", "install", MODULES[name]]
        elif name == "feroxbuster":
            builder = shutil.which("cargo")
            args = [builder or "cargo", "install", "--locked", "--root", str(destination.parent), "feroxbuster"]
        else:
            print(f"No installation recipe for {name}")
            return 1
        print(f"{name}: {shlex.join(args)}", flush=True)
        if not builder and not dry_run:
            print("Install a current Go toolchain and/or Rust Cargo first; see docs/INSTALL.md.")
            return 1
        plan.append((name, args, executable))
    if dry_run:
        print(f"Dry run: {len(plan)} missing tools; no downloads or changes made.")
        return 0
    destination.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "GOBIN": str(destination)}
    for name, args, executable in plan:
        print(f"Installing {name} into {destination}…", flush=True)
        try:
            subprocess.run(args, env=env, check=True)
        except (OSError, subprocess.CalledProcessError):
            print(f"Installation failed for {name}. Review the compiler output and retry; completed installs are retained.")
            return 1
        if not executable.is_file() or not os.access(executable, os.X_OK) or probe(name, str(executable), run=True)["compatibility"] != "compatible":
            print(f"{name} did not pass the adapter check. Review Toolchain before running it.")
            return 1
    print("Missing tools installed and checked. Refresh Toolchain or run: kiroshi doctor --require-tools")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Install missing workflow tools into ~/.local/bin; existing tools are not upgraded")
    parser.add_argument("--dry-run", action="store_true", help="Show missing tools and commands without downloading")
    parser.add_argument("--data-dir", default=str(default_data_dir()))
    args = parser.parse_args()
    paths = {}
    database = database_path(Path(args.data_dir).resolve())
    if database.exists():
        with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as connection:
            row = connection.execute("SELECT body FROM records WHERE kind='settings' AND id='local'").fetchone()
            paths = json.loads(row[0]).get("paths", {}) if row else {}
    raise SystemExit(install_missing(discover(paths, check=True), args.dry_run))


if __name__ == "__main__":
    main()
