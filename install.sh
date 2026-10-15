#!/usr/bin/env bash
set -euo pipefail

# Local launcher installation only: no sudo, package downloads, or security-tool installs.
KIROSHI_CHECKOUT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
KIROSHI_BIN_DIR="${HOME}/.local/bin"
KIROSHI_CREATE_LAUNCHER=1
while [ "$#" -gt 0 ]; do
  case "$1" in
    --bin-dir) [ "$#" -ge 2 ] || { echo 'Missing --bin-dir value' >&2; exit 1; }; KIROSHI_BIN_DIR="$2"; shift 2 ;;
    --check-only) KIROSHI_CREATE_LAUNCHER=0; shift ;;
    -h|--help) echo 'Usage: bash install.sh [--bin-dir DIRECTORY] [--check-only]'; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done
command -v python3 >/dev/null || { echo 'Install Python 3.10 or newer, then rerun this installer.' >&2; exit 1; }
python3 -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10 or newer is required"'
for KIROSHI_PREREQ in readlink sed tr date; do
  command -v "$KIROSHI_PREREQ" >/dev/null || { echo "Missing required utility: $KIROSHI_PREREQ (install GNU coreutils/sed)." >&2; exit 1; }
done
if [ "$KIROSHI_CREATE_LAUNCHER" -eq 1 ]; then
  mkdir -p -- "$KIROSHI_BIN_DIR"
  KIROSHI_LAUNCHER="$KIROSHI_BIN_DIR/kiroshi"
  if [ -e "$KIROSHI_LAUNCHER" ] || [ -L "$KIROSHI_LAUNCHER" ]; then
    [ -L "$KIROSHI_LAUNCHER" ] && [ "$(readlink -f -- "$KIROSHI_LAUNCHER")" = "$KIROSHI_CHECKOUT/kiroshi" ] || {
      echo "Refusing to overwrite an unrelated launcher: $KIROSHI_LAUNCHER" >&2
      echo 'Choose another --bin-dir or review the existing file yourself.' >&2
      exit 1
    }
  else
    ln -s -- "$KIROSHI_CHECKOUT/kiroshi" "$KIROSHI_LAUNCHER"
  fi
  echo "Launcher: $KIROSHI_LAUNCHER"
fi
cd -- "$KIROSHI_CHECKOUT"
python3 -m dashboard.doctor
echo
echo 'Start from this checkout: ./kiroshi'
echo 'Then open: http://localhost:8741'
echo 'Optional PATH setting: export PATH="$HOME/.local/bin:$PATH"'
echo 'The installer does not start a service, change shell files, or install scan tools.'
