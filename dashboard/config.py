"""Canonical names and non-destructive compatibility with existing local installs."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def environment(suffix, default=""):
    return os.environ.get("KIROSHI_" + suffix) or os.environ.get("HUNT_" + suffix) or default


def default_data_dir(root=None):
    root = Path(root) if root is not None else ROOT
    current, previous = root / ".kiroshi-data", root / ".hunt-data"
    return previous if previous.exists() and not current.exists() else current


def database_path(data):
    data = Path(data)
    current, previous = data / "kiroshi.sqlite3", data / "hunt.sqlite3"
    return previous if previous.exists() and not current.exists() else current
