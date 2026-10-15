#!/usr/bin/env bash
set -euo pipefail

# Local launcher installation only: no sudo, package downloads, or security-tool installs.
HUNT_CHECKOUT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
HUNT_BIN_DIR="${HOME}/.local/bin"
HUNT_CREATE_LAUNCHER=1
while [ "$#" -gt 0 ]; do
  case "$1" in
    --bin-dir) [ "$#" -ge 2 ] || { echo 'Missing --bin-dir value' >&2; exit 1; }; HUNT_BIN_DIR="$2"; shift 2 ;;
    --check-only) HUNT_CREATE_LAUNCHER=0; shift ;;
    -h|--help) echo 'Usage: bash install.sh [--bin-dir DIRECTORY] [--check-only]'; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done
command -v python3 >/dev/null || { echo 'Install Python 3.10 or newer, then rerun this installer.' >&2; exit 1; }
python3 -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10 or newer is required"'
for HUNT_PREREQ in readlink sed tr date; do
  command -v "$HUNT_PREREQ" >/dev/null || { echo "Missing required utility: $HUNT_PREREQ (install GNU coreutils/sed)." >&2; exit 1; }
done
if [ "$HUNT_CREATE_LAUNCHER" -eq 1 ]; then
  mkdir -p -- "$HUNT_BIN_DIR"
  HUNT_LAUNCHER="$HUNT_BIN_DIR/hunt-dashboard"
  if [ -e "$HUNT_LAUNCHER" ] || [ -L "$HUNT_LAUNCHER" ]; then
    [ -L "$HUNT_LAUNCHER" ] && [ "$(readlink -f -- "$HUNT_LAUNCHER")" = "$HUNT_CHECKOUT/hunt-dashboard" ] || {
      echo "Refusing to overwrite an unrelated launcher: $HUNT_LAUNCHER" >&2
      echo 'Choose another --bin-dir or review the existing file yourself.' >&2
      exit 1
    }
  else
    ln -s -- "$HUNT_CHECKOUT/hunt-dashboard" "$HUNT_LAUNCHER"
  fi
  echo "Launcher: $HUNT_LAUNCHER"
fi
cd -- "$HUNT_CHECKOUT"
python3 -m dashboard.doctor
echo
echo 'Start from this checkout: ./hunt-dashboard'
echo 'Then open: http://localhost:8741'
echo 'Optional PATH setting: export PATH="$HOME/.local/bin:$PATH"'
echo 'The installer does not start a service, change shell files, or install scan tools.'
