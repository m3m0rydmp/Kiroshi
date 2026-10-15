"""Bounded traffic settings and feedback from observable scanner output."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json

HTTP_TOOLS = {"httpx", "katana", "feroxbuster", "ffuf", "nuclei"}
DELAY_TOOLS = {"httpx", "katana", "ffuf", "tlsx"}
JITTER_TOOLS = {"ffuf"}
DEFAULTS = dict(concurrency=1, timeout=10, delay_ms=0, jitter_ms=0,
                stop_on_block=True, block_statuses=[429, 503], block_threshold=1, cooldown=30)


def integer(value, default, minimum, maximum, label):
    try:
        number = int(value if value not in (None, "") else default)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be an integer") from None
    if not minimum <= number <= maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}")
    return number


def normalize(value):
    if not isinstance(value, dict):
        raise ValueError("Traffic settings must be an object")
    result = {key: integer(value.get(key), default, lo, hi, key) for key, default, lo, hi in (
        ("concurrency", 1, 1, 10), ("timeout", 10, 3, 60), ("delay_ms", 0, 0, 60000),
        ("jitter_ms", 0, 0, 5000), ("block_threshold", 1, 1, 10), ("cooldown", 30, 1, 3600))}
    statuses = value.get("block_statuses", [429, 503])
    if not isinstance(statuses, list) or not statuses or any(type(code) is not int or code not in (403, 429, 503) for code in statuses):
        raise ValueError("Block statuses must contain 403, 429 and/or 503")
    result["block_statuses"] = list(dict.fromkeys(statuses))
    result["stop_on_block"] = value.get("stop_on_block", True) is True
    return result


def effective(engagement, payload):
    result = normalize(engagement.get("traffic", {}))
    ceiling = engagement["rate"]
    profile = payload.get("traffic_profile", "inherit")
    if profile not in ("inherit", "gentle"):
        raise ValueError("Select inherited settings or the gentle profile")
    result["rate"] = integer(payload.get("rate"), ceiling, 1, ceiling, "Run request rate")
    result["delay_ms"] = integer(payload.get("delay_ms"), result["delay_ms"], 0, 60000, "Run delay")
    result["jitter_ms"] = integer(payload.get("jitter_ms"), result["jitter_ms"], 0, 5000, "Run jitter")
    if profile == "gentle":
        result.update(rate=1, concurrency=1, delay_ms=0, jitter_ms=0)
    result["profile"] = profile
    tool = payload.get("tool")
    if tool == "tlsx":
        result["concurrency"] = 1
    if result["delay_ms"] and tool not in DELAY_TOOLS:
        raise ValueError(f"{tool} has no supported delay control; use its rate limit and set delay to zero")
    if result["jitter_ms"] and tool not in JITTER_TOOLS:
        raise ValueError(f"{tool} has no supported jitter control; jitter is currently available for ffuf only")
    return result


def retry_after(value, clock=None):
    """Return a delay or a manual hold for unreasonably long server requests."""
    if value is None:
        return 0, False
    try:
        seconds = int(str(value).strip())
    except ValueError:
        try:
            parsed = parsedate_to_datetime(str(value))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            seconds = int((parsed - (clock or datetime.now(timezone.utc))).total_seconds())
        except (ValueError, TypeError, OverflowError):
            return 0, False
    if seconds > 86400:
        return 0, True  # Never silently shorten a server's long cooldown.
    return max(0, seconds), False


class Feedback:
    def __init__(self, settings):
        self.settings = settings
        self.consecutive = 0
        self.events = []

    def observe(self, text):
        for line in text.splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if not isinstance(row, dict):
                continue
            response = row.get("response") if isinstance(row.get("response"), dict) else {}
            status = row.get("status_code", row.get("status", response.get("status_code")))
            try:
                status = int(status)
            except (ValueError, TypeError):
                continue
            if status not in self.settings["block_statuses"]:
                self.consecutive = 0
                continue
            self.consecutive += 1
            headers = response.get("headers") or row.get("headers") or row.get("header") or {}
            retry = None
            if isinstance(headers, dict):
                retry = next((value for key, value in headers.items() if key.lower().replace("_", "-") == "retry-after"), None)
                if isinstance(retry, list):
                    retry = retry[0] if retry else None
            seconds, manual = retry_after(retry)
            event = dict(status_code=status, delay=max(self.settings["cooldown"], seconds),
                         manual_hold=manual, reason="HTTP throttling/service-denial signal; WAF attribution is not established")
            self.events.append(event)
            self.events = self.events[-25:]
            if self.settings["stop_on_block"] and self.consecutive >= self.settings["block_threshold"]:
                return event
        return None
