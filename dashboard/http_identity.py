"""Consistent browser-style HTTP identity for application-controlled requests."""
from functools import lru_cache
import os
import re
import shutil
import subprocess
from .config import environment


@lru_cache(maxsize=1)
def browser_user_agent():
    override = environment("USER_AGENT").strip()
    if override:
        if len(override) > 512 or any(ord(c) < 32 or ord(c) > 126 for c in override):
            raise ValueError("KIROSHI_USER_AGENT must be a printable, single-line browser User-Agent")
        return override
    major = "154"  # Fallback when Chrome is absent; customize with KIROSHI_USER_AGENT.
    chrome = shutil.which("google-chrome") or shutil.which("chromium")
    if chrome:
        try:
            result = subprocess.run([chrome, "--version"], capture_output=True, text=True, timeout=3, check=True)
            match = re.search(r"\b(\d+)\.\d+\.\d+\.\d+", result.stdout)
            if match:
                major = match[1]
        except (OSError, subprocess.SubprocessError):
            pass
    # Current Chrome reduces its public UA version to major.0.0.0.
    return f"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{major}.0.0.0 Safari/537.36"
