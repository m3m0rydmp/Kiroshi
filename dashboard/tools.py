"""Explicit tool adapters; no user-supplied shell commands."""
import ipaddress
import os
from pathlib import Path
import re
import shutil
from urllib.parse import urlsplit
from .http_identity import browser_user_agent

ROOT = Path(__file__).resolve().parent.parent
CATALOG = {
    "subfinder": ("Recon", "Passive subdomain discovery", True),
    "dnsx": ("DNS", "Resolve A, AAAA and CNAME records", True),
    "httpx": ("HTTP", "HTTP status, titles and technology inventory", True),
    "tlsx": ("TLS", "Certificate and TLS inventory", True),
    "katana": ("Crawling", "Scoped, depth-limited URL crawling", True),
    "feroxbuster": ("Discovery", "Non-recursive content discovery", True),
    "ffuf": ("Discovery", "Bounded GET path discovery", True),
    "nuclei": ("Templates", "Bundled HTTP server-header inventory template", True),
    "amass": ("Recon", "Asset discovery", False),
    "findomain": ("Recon", "Passive subdomain discovery", False),
    "assetfinder": ("Recon", "Related asset discovery", False),
    "chaos-client": ("Recon", "ProjectDiscovery dataset lookup", False),
    "urlfinder": ("Recon", "Passive URL collection", False),
    "gau": ("Archives", "Historical URL collection", False),
    "waybackurls": ("Archives", "Wayback URL collection", False),
    "puredns": ("DNS", "Wildcard-aware DNS resolution", False),
    "shuffledns": ("DNS", "MassDNS wrapper", False),
    "dnsgen": ("DNS", "DNS name permutations", False),
    "alterx": ("DNS", "Subdomain permutations", False),
    "naabu": ("Ports", "Port discovery", False),
    "nmap": ("Ports", "Service inventory", False),
    "arjun": ("Parameters", "HTTP parameter discovery", False),
    "paramspider": ("Parameters", "Archived parameter discovery", False),
    "dalfox": ("Testing", "XSS testing", False),
    "sqlmap": ("Testing", "SQL injection testing", False),
    "crlfuzz": ("Testing", "CRLF testing", False),
    "interactsh-client": ("OOB", "Out-of-band interaction tracking", False),
    "gitleaks": ("Secrets", "Local repository secret scanning", False),
    "trufflehog": ("Secrets", "Secret discovery and verification", False),
    "jq": ("Utilities", "JSON processing", False),
    "anew": ("Utilities", "Deduplicate streams", False),
    "uro": ("Utilities", "URL deduplication", False),
    "unfurl": ("Utilities", "URL parsing", False),
    "notify": ("Utilities", "Notification delivery", False),
    "claude": ("Agents", "Claude Code / your configured provider", False),
    "codex": ("Agents", "Codex CLI", False),
}


def discover(overrides=None):
    overrides = overrides or {}
    dirs = [str(Path.home() / p) for p in (".pdtm/go/bin", "go/bin", ".cargo/bin", ".local/bin")]
    search = os.pathsep.join(dirs + [os.environ.get("PATH", "")])
    tools = []
    for name, (category, description, adapter) in CATALOG.items():
        path = overrides.get(name) or shutil.which(name, path=search)
        found = bool(path and Path(path).is_file() and os.access(path, os.X_OK))
        tools.append(dict(name=name, category=category, description=description,
                          adapter=adapter, installed=found, path=str(path) if found else None))
    return tools


def host(value):
    value = str(value).strip().lower().rstrip(".")
    if not value or any(c in value for c in "\r\n\t /@?#\\%"):
        raise ValueError("Use a hostname or IP, without a path, port, or URL")
    try:
        return str(ipaddress.ip_address(value.strip("[]")))
    except ValueError:
        value = value.encode("idna").decode("ascii")
        if len(value) > 253 or not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", part) for part in value.split(".")):
            raise ValueError("Invalid hostname")
        return value


def rules(text):
    values = text if isinstance(text, list) else re.split(r"[\s,]+", str(text).strip())
    result = []
    for raw in values:
        if not raw:
            continue
        wildcard = raw.startswith("*.")
        normalized = host(raw[2:] if wildcard else raw)
        if wildcard:
            try:
                ipaddress.ip_address(normalized)
            except ValueError:
                pass
            else:
                raise ValueError("IP wildcards are unsupported")
        result.append(("*." if wildcard else "") + normalized)
    return list(dict.fromkeys(result))


def matches(name, rule):
    return name.endswith("." + rule[2:]) if rule.startswith("*.") else name == rule


def allowed(name, engagement):
    return any(matches(name, r) for r in engagement["scope"]) and not any(matches(name, r) for r in engagement["excluded"])


def target_url(value, engagement):
    value = str(value).strip()
    if any(c.isspace() or ord(c) < 32 for c in value) or "\\" in value:
        raise ValueError("Invalid target URL")
    parsed = urlsplit(value if "://" in value else "https://" + value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username is not None or parsed.password is not None:
        raise ValueError("Use an http(s) URL without credentials")
    name = host(parsed.hostname)
    if not allowed(name, engagement):
        raise ValueError("Target is outside the engagement scope or explicitly excluded")
    port = parsed.port
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("Invalid port")
    netloc = f"[{name}]" if ":" in name else name
    if port:
        netloc += f":{port}"
    return parsed._replace(netloc=netloc, fragment="").geturl(), name, port


def command(engagement, payload, tools):
    tool = payload.get("tool")
    item = next((t for t in tools if t["name"] == tool), None)
    if not item or not item["adapter"]:
        raise ValueError("This tool is inventory-only; an adapter is required")
    if not item["installed"]:
        raise ValueError("Tool not installed; configure its executable path in Toolchain")
    rate = str(engagement["rate"])
    url, name, port = target_url(payload.get("target", ""), engagement)
    exe = item["path"]
    duration = engagement["duration"]
    common = ["-silent", "-duc"]
    wordlist = str(ROOT / "dashboard" / "wordlist.txt")
    if tool == "subfinder":
        # Passive collection may discover excluded names, but never probes them.
        args = [exe, "-d", name, *common, "-rl", rate, "-timeout", "10", "-max-time", "2"]
    elif tool == "dnsx":
        args = [exe, "-l", name, *common, "-a", "-aaaa", "-cname", "-j", "-t", "1", "-rl", rate]
    elif tool == "httpx":
        args = [exe, "-u", url, *common, "-j", "-sc", "-title", "-td", "-location", "-t", "1", "-rl", rate, "-timeout", "10", "-retries", "0", "-nfs"]
    elif tool == "tlsx":
        args = [exe, "-u", name, "-p", str(port or 443), *common, "-j", "-san", "-cn", "-tv", "-c", "1", "-retry", "0", "-timeout", "10", "-delay", f"{1 / engagement['rate']:.3f}s"]
    elif tool == "katana":
        # Crawl only the selected origin, even if engagement scope is broader.
        parsed = urlsplit(url)
        origin = re.escape(f"{parsed.scheme}://{parsed.netloc}")
        args = [exe, "-u", url, *common, "-j", "-dr", "-d", "2", "-cs", f"^{origin}(?:/|$)", "-c", "1", "-p", "1", "-rl", rate, "-ct", f"{duration}s", "-timeout", "10", "-retry", "0"]
    elif tool == "feroxbuster":
        args = [exe, "-u", url, "-w", wordlist, "--no-recursion", "--dont-extract-links", "--no-state", "--rate-limit", rate, "--threads", "1", "--time-limit", f"{duration}s", "--timeout", "10", "--json", "--silent"]
    elif tool == "ffuf":
        if urlsplit(url).query:
            raise ValueError("Path discovery targets cannot contain a query")
        args = [exe, "-u", url.rstrip("/") + "/FUZZ", "-w", wordlist, "-rate", rate, "-t", "1", "-maxtime", str(duration), "-timeout", "10", "-json", "-noninteractive"]
    else:
        args = [exe, "-u", url, "-t", str(ROOT / "dashboard" / "templates" / "server-header.yaml"), *common, "-j", "-nc", "-dr", "-ni", "-nh", "-no-stdin", "-rl", rate, "-c", "1", "-bs", "1", "-timeout", "10", "-retries", "0"]
    user_agent = browser_user_agent()
    if tool in ("httpx", "katana", "nuclei", "ffuf"):
        args += ["-H", "User-Agent: " + user_agent]
    elif tool == "feroxbuster":
        args += ["--user-agent", user_agent]
    return args
