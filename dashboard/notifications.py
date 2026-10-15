"""Private webhook settings and a bounded dispatcher independent of scan execution."""
from datetime import datetime, timezone
import html
import json
import os
from pathlib import Path
import queue
import re
import threading
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, parse_qsl, urlencode, urlsplit
from urllib.request import build_opener, ProxyHandler, Request

from .http_identity import browser_user_agent
from .references import NoRedirect

EVENTS = {"workflow_completed", "workflow_stopped", "job_completed", "job_stopped"}


def normalize(payload):
    value = str(payload.get("url", "")).strip()
    parsed = urlsplit(value)
    if (len(value) > 4096 or parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username is not None or parsed.password is not None
            or parsed.fragment or any(c.isspace() or ord(c) < 32 for c in value) or "\\" in value):
        raise ValueError("Use an HTTP(S) webhook URL without credentials, whitespace or fragments")
    if parsed.port is not None and not 1 <= parsed.port <= 65535:
        raise ValueError("Invalid webhook port")
    if parsed.scheme != "https" and parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("Use HTTPS for remote webhook endpoints")
    events = payload.get("events", ["workflow_completed", "workflow_stopped"])
    if not isinstance(events, list) or any(event not in EVENTS for event in events):
        raise ValueError("Choose supported notification events")
    platform = "generic"
    extras = {}
    if parsed.hostname in ("discord.com", "discordapp.com", "canary.discord.com", "ptb.discord.com"):
        if not re.fullmatch(r"/api(?:/v[0-9]+)?/webhooks/[0-9]+/[A-Za-z0-9_.-]+/?", parsed.path):
            raise ValueError("Paste a Discord webhook URL from the channel integration settings")
        platform = "discord"
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query["wait"] = "true"
        value = parsed._replace(query=urlencode(query)).geturl()
    elif parsed.hostname == "hooks.slack.com":
        if not parsed.path.startswith("/services/"):
            raise ValueError("Paste a Slack incoming webhook URL")
        platform = "slack"
    elif parsed.hostname == "api.telegram.org":
        if not re.fullmatch(r"/bot[0-9]+:[A-Za-z0-9_-]+/sendMessage", parsed.path):
            raise ValueError("Use https://api.telegram.org/botTOKEN/sendMessage?chat_id=YOUR_CHAT_ID")
        query = parse_qs(parsed.query)
        chat = query.get("chat_id", [])
        if len(chat) != 1 or not re.fullmatch(r"(?:-?[0-9]+|@[A-Za-z0-9_]+)", chat[0]):
            raise ValueError("Telegram requires one chat_id in the pasted URL")
        extras["chat_id"] = chat[0]
        topic = query.get("message_thread_id", [])
        if topic:
            if len(topic) != 1 or not topic[0].isdigit():
                raise ValueError("Telegram message_thread_id must be numeric")
            extras["message_thread_id"] = int(topic[0])
        value = parsed._replace(query="").geturl()
        platform = "telegram"
    return dict(url=value, host=parsed.hostname, platform=platform, enabled=payload.get("enabled", True) is True,
                events=list(dict.fromkeys(events)), **extras)


def formatted(config, event):
    title = str(event.get("title", "Kiroshi notification"))[:200]
    fields = [("Engagement", event.get("engagement", "Local workspace")), ("Status", event.get("status", "test"))]
    for label, key in (("Tool", "tool"), ("Target", "target"), ("Stage", "stage"), ("Tool jobs", "jobs"), ("Duration", "duration")):
        if event.get(key) is not None:
            fields.append((label, str(event[key])[:300]))
    detail = str(event.get("summary", "Your Kiroshi webhook is connected."))[:1000]
    failed = event.get("status") not in ("completed", "test", "completed_limited")
    icon = "⚠" if failed else "✓"
    text = f"{icon} {title}\n" + "\n".join(f"{label}: {value}" for label, value in fields) + "\n\n" + detail
    if config["platform"] == "discord":
        return {"username": "Kiroshi", "allowed_mentions": {"parse": []}, "embeds": [{"title": f"{icon} {title}", "description": detail,
                "color": 16748185 if failed else 11856886, "fields": [{"name": label, "value": str(value) or "—", "inline": True} for label, value in fields],
                "footer": {"text": "Kiroshi • Local engagement workflow"}, "timestamp": datetime.now(timezone.utc).isoformat()}]}
    if config["platform"] == "telegram":
        return {"chat_id": config["chat_id"], **({"message_thread_id": config["message_thread_id"]} if "message_thread_id" in config else {}),
                "parse_mode": "HTML", "disable_web_page_preview": True,
                "text": f"<b>{html.escape(icon + ' ' + title)}</b>\n\n" + "\n".join(f"<b>{label}</b>: {html.escape(str(value))}" for label, value in fields) + "\n\n" + html.escape(detail)}
    if config["platform"] == "slack":
        return {"text": text, "unfurl_links": False, "unfurl_media": False, "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": f"{icon} {title}"[:150]}},
            {"type": "section", "fields": [{"type": "plain_text", "text": f"{label}\n{value}"} for label, value in fields]},
            {"type": "section", "text": {"type": "plain_text", "text": detail}}]}
    return {"source": "Kiroshi", "event": event.get("event", "test"), "title": title, "text": text,
            "fields": dict(fields), "summary": detail, "timestamp": datetime.now(timezone.utc).isoformat()}


class Notifications:
    def __init__(self, data):
        self.file = Path(data) / "secrets" / "notifications.json"
        self.lock = threading.RLock()
        self.config = None
        self.last_delivery = None
        try:
            if self.file.exists():
                loaded = json.loads(self.file.read_text())
                self.config = loaded if isinstance(loaded, dict) and "url" in loaded and "events" in loaded else None
        except (OSError, ValueError):
            self.last_delivery = dict(status="failed", error="Saved notification settings could not be loaded; save the webhook again")
        self.revision = 0
        self.queue = queue.Queue(maxsize=128)
        self.seen = set()
        self.stopped = False
        self.worker = threading.Thread(target=self.work, daemon=True)
        self.worker.start()

    def public(self):
        with self.lock:
            config = self.config or {}
            return dict(configured=bool(self.config), platform=config.get("platform", "generic"), host=config.get("host", ""),
                        enabled=config.get("enabled", False), events=config.get("events", []), last_delivery=self.last_delivery)

    def save(self, payload):
        with self.lock:
            if payload.get("remove") is True:
                self.file.unlink(missing_ok=True)
                self.config = None
            else:
                if not str(payload.get("url", "")).strip() and self.config:
                    # Toggle event settings without returning or re-entering the secret URL.
                    config = {**self.config, "enabled": payload.get("enabled") is True}
                    events = payload.get("events", [])
                    if not isinstance(events, list) or any(event not in EVENTS for event in events):
                        raise ValueError("Invalid notification events")
                    config["events"] = list(dict.fromkeys(events))
                else:
                    config = normalize(payload)
                self.file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                temporary = self.file.with_suffix(".tmp")
                descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                with os.fdopen(descriptor, "w") as stream:
                    json.dump(config, stream)
                os.replace(temporary, self.file)
                self.file.chmod(0o600)
                self.config = config
            self.last_delivery = None
            self.revision += 1
        return self.public()

    def send(self, event):
        with self.lock:
            config = dict(self.config) if self.config else None
        if not config:
            raise ValueError("Save a webhook URL first")
        request = Request(config["url"], data=json.dumps(formatted(config, event)).encode(), headers={"Content-Type": "application/json", "User-Agent": browser_user_agent()}, method="POST")
        try:
            with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=8) as response:
                raw = response.read(65536)
                if not 200 <= response.status < 300:
                    raise ValueError("The webhook did not accept the notification")
                if config["platform"] == "telegram":
                    result = json.loads(raw)
                    if not isinstance(result, dict) or result.get("ok") is not True:
                        raise ValueError("Telegram did not accept the message; check the bot token and chat_id")
        except HTTPError as exc:
            raise ValueError(f"Webhook returned HTTP {exc.code}; verify its URL and platform permissions") from None
        except (URLError, TimeoutError, OSError, json.JSONDecodeError):
            raise ValueError("Could not deliver the notification; check webhook connectivity and settings") from None
        return dict(ok=True, platform=config["platform"], message="Test notification sent" if event.get("event") == "test" else "Notification sent")

    def enqueue(self, event):
        with self.lock:
            if self.stopped or not self.config or not self.config["enabled"] or event["event"] not in self.config["events"] or event["id"] in self.seen:
                return
            try:
                self.queue.put_nowait({**event, "_revision": self.revision})
            except queue.Full:
                self.last_delivery = dict(status="failed", error="Notification queue is full")
                return
            self.seen.add(event["id"])
            if len(self.seen) > 2000:
                self.seen = {event["id"]}

    def work(self):
        while True:
            event = self.queue.get()
            if event is None:
                return
            try:
                with self.lock:
                    enabled = self.config and self.config["enabled"] and event["event"] in self.config["events"] and event["_revision"] == self.revision
                if enabled and not self.stopped:
                    self.send(event)
                    self.last_delivery = dict(status="sent", at=datetime.now(timezone.utc).isoformat())
            except Exception:
                self.last_delivery = dict(status="failed", error="Delivery failed; check the webhook using Send test notification", at=datetime.now(timezone.utc).isoformat())

    def close(self):
        self.stopped = True
        try:
            self.queue.put_nowait(None)
        except queue.Full:
            pass
        self.worker.join(timeout=1)
