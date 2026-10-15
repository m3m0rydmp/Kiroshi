"""Explicit tool adapters; no user-supplied shell commands."""
import ipaddress
import os
from pathlib import Path
import re
import subprocess
import math
from urllib.parse import urlsplit
from .http_identity import browser_user_agent
from .traffic import effective

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
    "urlfinder": ("Recon", "Passive URL collection", True),
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


SIGNATURES = {
    "urlfinder": ("-max-time", "-url-scope", "-rate-limit"),
    "subfinder": ("-max-time", "-rate-limit"), "dnsx": ("-rcode", "-resp-only"),
    "httpx": ("-status-code", "-no-fallback-scheme"), "tlsx": ("-tls-version", "-scan-mode"),
    "katana": ("-crawl-scope", "-disable-redirects"), "feroxbuster": ("--no-recursion", "--rate-limit"),
    "ffuf": ("-maxtime", "-noninteractive"), "nuclei": ("-no-interactsh", "-disable-redirects"),
}
_PROBES = {}


def probe(name, path, run=False):
    if name not in SIGNATURES or not path:
        return {"compatibility": "not_checked", "diagnostic": "No adapter compatibility check available"}
    try:
        stat = Path(path).stat()
    except OSError:
        return {"compatibility": "incompatible", "diagnostic": "Executable is unavailable"}
    key = (name, path, stat.st_mtime_ns, stat.st_size)
    if key not in _PROBES and run:
        try:
            result = subprocess.run([path, "--help" if name == "feroxbuster" else "-h"],
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, errors="replace", timeout=3, stdin=subprocess.DEVNULL)
            missing = [flag for flag in SIGNATURES[name] if flag not in result.stdout]
            _PROBES[key] = dict(compatibility="incompatible" if missing else "compatible",
                                diagnostic="Missing expected help flags: " + ", ".join(missing) if missing else "Expected adapter flags detected")
        except (OSError, subprocess.SubprocessError):
            _PROBES[key] = dict(compatibility="incompatible", diagnostic="Could not read help within 3 seconds")
    return _PROBES.get(key, dict(compatibility="not_checked", diagnostic="Run Check binaries or the installation doctor"))


def discover(overrides=None, check=False):
    overrides = overrides or {}
    dirs = [str(Path.home() / p) for p in (".pdtm/go/bin", "go/bin", ".cargo/bin", ".local/bin")]
    if os.environ.get("GOBIN"):
        dirs.insert(0, os.environ["GOBIN"])
    dirs += [str(Path(p) / "bin") for p in os.environ.get("GOPATH", "").split(os.pathsep) if p]
    dirs += os.environ.get("PATH", "").split(os.pathsep)
    dirs = list(dict.fromkeys(os.path.abspath(os.path.expanduser(p)) for p in dirs if p))
    tools = []
    for name, (category, description, adapter) in CATALOG.items():
        candidates = [str(Path(directory) / name) for directory in dirs
                      if (Path(directory) / name).is_file() and os.access(Path(directory) / name, os.X_OK)]
        # Python's unrelated httpx CLI commonly shadows ProjectDiscovery httpx.
        detected = next((p for p in candidates if name != "httpx" or probe(name, p, run=True)["compatibility"] == "compatible"), None)
        override = overrides.get(name)
        valid_override = bool(override and Path(override).is_file() and os.access(override, os.X_OK))
        path = override if valid_override else detected
        found = bool(path)
        diagnostic = probe(name, path, run=check and adapter)
        tools.append(dict(name=name, category=category, description=description,
                          adapter=adapter, installed=found, path=path,
                          detected_path=detected, configured_path=override,
                          override_active=valid_override,
                          source="override" if valid_override else "autodetected" if found else "missing",
                          override_warning="Saved path is unavailable; using autodetection" if override and not valid_override else None,
                          runnable=bool(found and adapter and diagnostic["compatibility"] != "incompatible"),
                          **diagnostic))
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
        raw = str(raw).strip()
        if any(c.isspace() or ord(c) < 32 for c in raw):
            raise ValueError("Scope entries cannot contain whitespace")
        prefix = ""
        suffix = ""
        if "://" in raw:
            parsed = urlsplit(raw)
            if (parsed.scheme not in ("http", "https") or not parsed.hostname
                    or parsed.username is not None or parsed.password is not None
                    or parsed.query or parsed.fragment or "\\" in raw
                    or "%" in parsed.path or any(p in (".", "..") for p in parsed.path.split("/"))):
                raise ValueError("Scope URLs must use HTTP(S), without credentials, queries, fragments or encoded paths")
            port = parsed.port
            if port is not None and not 1 <= port <= 65535:
                raise ValueError("Invalid scope port")
            prefix = parsed.scheme + "://"
            suffix = (":" + str(port) if port is not None else "") + (parsed.path.rstrip("/") or "")
            if not suffix:
                # A root URL is a convenient way to paste a host scope.
                prefix = ""
            raw = parsed.hostname
        wildcard = raw.startswith("*.")
        normalized = host(raw[2:] if wildcard else raw)
        if wildcard:
            try:
                ipaddress.ip_address(normalized)
            except ValueError:
                pass
            else:
                raise ValueError("IP wildcards are unsupported")
        normalized = ("*." if wildcard else "") + normalized
        if prefix:
            normalized = "[" + normalized + "]" if ":" in normalized else normalized
        result.append(prefix + normalized + suffix)
    return list(dict.fromkeys(result))


def matches(name, rule):
    # URL rules retain scheme, port and path; host-only checks cannot grant them.
    if "://" in rule:
        return False
    return name.endswith("." + rule[2:]) if rule.startswith("*.") else name == rule


def url_rule_matches(value, rule):
    if "://" not in rule:
        return matches(host(urlsplit(value).hostname), rule)
    target, boundary = urlsplit(value), urlsplit(rule)
    if (target.scheme != boundary.scheme
            or (target.port or (443 if target.scheme == "https" else 80)) != (boundary.port or (443 if boundary.scheme == "https" else 80))
            or not matches(host(target.hostname), boundary.hostname)):
        return False
    path = boundary.path.rstrip("/")
    return not path or target.path == path or target.path.startswith(path + "/")


def allowed(name, engagement):
    return any(matches(name, r) for r in engagement["scope"]) and not any(
        matches(name, urlsplit(r).hostname if "://" in r else r) for r in engagement["excluded"])



def target_url(value, engagement):
    value = str(value).strip()
    if any(c.isspace() or ord(c) < 32 for c in value) or "\\" in value:
        raise ValueError("Invalid target URL")
    if "://" not in value:
        try:
            address = ipaddress.ip_address(value.strip("[]"))
            if address.version == 6:
                value = f"[{address}]"
        except ValueError:
            pass
    parsed = urlsplit(value if "://" in value else "https://" + value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username is not None or parsed.password is not None:
        raise ValueError("Use an http(s) URL without credentials")
    name = host(parsed.hostname)
    port = parsed.port
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("Invalid port")
    netloc = f"[{name}]" if ":" in name else name
    if port:
        netloc += f":{port}"
    url = parsed._replace(netloc=netloc, fragment="").geturl()
    if not any(url_rule_matches(url, r) for r in engagement["scope"]) or any(url_rule_matches(url, r) for r in engagement["excluded"]):
        raise ValueError("Target is outside the engagement scope or explicitly excluded")
    restricted = any("://" in r and urlsplit(r).path for r in engagement["scope"] + engagement["excluded"])
    if restricted and ("%" in parsed.path or any(p in (".", "..") for p in parsed.path.split("/"))):
        raise ValueError("Use a literal path without traversal or percent encoding for URL-restricted scope")
    return url, name, port


def passive_seed(value, engagement):
    try:
        name = host(value)
        ipaddress.ip_address(name)
        return False
    except ValueError:
        pass
    try:
        name = host(value)
    except ValueError:
        return False
    return "*." + name in engagement["scope"] and not any(
        matches(name, urlsplit(r).hostname if "://" in r else r) for r in engagement["excluded"])


def resolve_target(engagement, payload):
    value = payload.get("target", "")
    if payload.get("tool") in ("subfinder", "urlfinder") and passive_seed(value, engagement):
        # Passive collection queries third-party sources; this grants no apex probing.
        return target_url(value, {"scope": [host(value)], "excluded": []})
    return target_url(value, engagement)


def command(engagement, payload, tools):
    tool = payload.get("tool")
    item = next((t for t in tools if t["name"] == tool), None)
    if not item or not item["adapter"]:
        raise ValueError("This tool is inventory-only; an adapter is required")
    if not item["installed"]:
        raise ValueError("Tool not installed; configure its executable path in Toolchain")
    if item.get("compatibility") == "incompatible":
        raise ValueError("Tool is incompatible with its adapter: " + item["diagnostic"])
    traffic = effective(engagement, payload)
    rate, concurrency, timeout = str(traffic["rate"]), str(traffic["concurrency"]), str(traffic["timeout"])
    url, name, port = resolve_target(engagement, payload)
    # Current adapters can crawl, probe alternate paths, or discard URL boundaries.
    # Require whole-host authorization until each supports a request-level scope gate.
    if not allowed(name, engagement) and not (tool in ("subfinder", "urlfinder") and passive_seed(payload.get("target", ""), engagement)):
        raise ValueError("This adapter requires whole-host scope; URL-only scope is saved but cannot be scanned by current adapters")
    exe = item["path"]
    duration = engagement["duration"]
    common = ["-silent", "-duc"]
    wordlist = str(ROOT / "dashboard" / "wordlist.txt")
    if tool == "urlfinder":
        args = [exe, "-d", name, *common, "-j", "-rl", rate, "-timeout", timeout, "-max-time", "2", "-us", r"^https?://(?:[^/]+\.)?" + re.escape(name) + r"(?::[0-9]+)?(?:/|$)"]
    elif tool == "subfinder":
        # Passive collection may discover excluded names, but never probes them.
        args = [exe, "-d", name, *common, "-rl", rate, "-timeout", timeout, "-max-time", "2"]
    elif tool == "dnsx":
        args = [exe, "-l", name, *common, "-a", "-aaaa", "-cname", "-j", "-t", concurrency, "-rl", rate, "-timeout", timeout + "s"]
    elif tool == "httpx":
        args = [exe, "-u", url, *common, "-j", "-sc", "-title", "-td", "-location", "-irh", "-t", concurrency, "-rl", rate, "-timeout", timeout, "-retries", "0", "-nfs"]
        if traffic["delay_ms"]:
            args += ["-delay", f"{traffic['delay_ms']}ms"]
    elif tool == "tlsx":
        delay = max(1 / traffic["rate"], traffic["delay_ms"] / 1000)
        # JSON already contains subject_cn/subject_an. SAN/CN output filters
        # cannot be combined with TLS probes in current tlsx releases.
        args = [exe, "-u", name, "-p", str(port or 443), *common, "-j", "-tv", "-c", "1", "-retry", "0", "-timeout", timeout, "-delay", f"{delay:.3f}s"]
    elif tool == "katana":
        # Crawl only the selected origin, even if engagement scope is broader.
        parsed = urlsplit(url)
        origin = re.escape(f"{parsed.scheme}://{parsed.netloc}")
        args = [exe, "-u", url, *common, "-j", "-dr", "-d", "2", "-cs", f"^{origin}(?:/|$)", "-c", concurrency, "-p", "1", "-rl", rate, "-ct", f"{duration}s", "-timeout", timeout, "-retry", "0"]
        if traffic["delay_ms"]:
            args += ["-rd", str(math.ceil(traffic["delay_ms"] / 1000))]
    elif tool == "feroxbuster":
        args = [exe, "-u", url, "-w", wordlist, "--no-recursion", "--dont-extract-links", "--no-state", "--rate-limit", rate, "--threads", concurrency, "--scan-limit", "1", "--auto-bail" if traffic["stop_on_block"] else "--auto-tune", "--time-limit", f"{duration}s", "--timeout", timeout, "--json", "--silent"]
    elif tool == "ffuf":
        if urlsplit(url).query:
            raise ValueError("Path discovery targets cannot contain a query")
        args = [exe, "-u", url.rstrip("/") + "/FUZZ", "-w", wordlist, "-rate", rate, "-t", concurrency, "-maxtime", str(duration), "-timeout", timeout, "-mc", "all", "-json", "-noninteractive"]
        if traffic["delay_ms"] or traffic["jitter_ms"]:
            start, end = traffic["delay_ms"] / 1000, (traffic["delay_ms"] + traffic["jitter_ms"]) / 1000
            args += ["-p", f"{start:.3f}-{end:.3f}" if end > start else f"{start:.3f}"]
    else:
        args = [exe, "-u", url, "-t", str(ROOT / "dashboard" / "templates" / "server-header.yaml"), *common, "-j", "-nc", "-dr", "-ni", "-nh", "-no-stdin", "-rl", rate, "-c", concurrency, "-bs", "1", "-timeout", timeout, "-retries", "0"]
    if payload.get("diagnostics") is True:
        args = [arg for arg in args if arg not in ("-silent", "--silent")]
        if tool in ("httpx", "nuclei"):
            args += ["-stats", "-si", "2"]
        elif tool in ("dnsx", "subfinder", "urlfinder"):
            args += ["-stats"]
        elif tool == "ffuf":
            args += ["-v"]
    user_agent = browser_user_agent()
    if tool in ("httpx", "katana", "nuclei", "ffuf"):
        args += ["-H", "User-Agent: " + user_agent]
    elif tool == "feroxbuster":
        args += ["--user-agent", user_agent]
    return args
