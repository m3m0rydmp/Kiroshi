"""Bounded public HackerOne metadata collection. Never sends engagement sessions."""
import base64
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
import re
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import build_opener, HTTPRedirectHandler, ProxyHandler, Request
from .http_identity import browser_user_agent
from .config import environment

MAX_BYTES = 2 * 1024 * 1024


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def report_id(value):
    value = str(value).strip()
    if re.fullmatch(r"[1-9][0-9]{0,11}", value):
        return value
    parsed = urlsplit(value)
    if parsed.scheme != "https" or parsed.netloc != "hackerone.com" or parsed.query or parsed.fragment:
        raise ValueError("Use a public https://hackerone.com/reports/NUMBER URL or numeric report ID")
    match = re.fullmatch(r"/reports/([1-9][0-9]{0,11})(?:\.json)?/?", parsed.path)
    if not match:
        raise ValueError("Only numeric HackerOne report URLs are supported")
    return match[1]


def read_json(url, authorization=None):
    headers = {"User-Agent": browser_user_agent(), "Accept": "application/json"}
    if authorization:
        headers["Authorization"] = authorization
    opener = build_opener(ProxyHandler({}), NoRedirect())
    try:
        with opener.open(Request(url, headers=headers), timeout=8) as response:
            raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError("Reference response exceeded the 2 MiB limit")
            return json.loads(raw)
    except HTTPError as exc:
        raise ValueError(f"HackerOne returned HTTP {exc.code}; no authentication/anti-bot bypass was attempted") from None
    except (URLError, TimeoutError, json.JSONDecodeError):
        raise ValueError("Could not read public HackerOne JSON; try later or use another publicly disclosed report") from None


def normalize(report, expected):
    if not isinstance(report, dict) or str(report.get("id")) != expected:
        raise ValueError("Report identifier does not match the requested source")
    if report.get("public") is not True or not report.get("disclosed_at"):
        raise ValueError("Only reports explicitly marked public and disclosed can be imported")
    amount = None
    try:
        candidate = Decimal(str(report.get("bounty_amount")))
        if candidate.is_finite() and candidate >= 0:
            amount = str(candidate)
    except InvalidOperation:
        pass
    team = report.get("team") if isinstance(report.get("team"), dict) else {}
    weakness = report.get("weakness") if isinstance(report.get("weakness"), dict) else {}
    # Retain a short attributed excerpt, never attachments or the full discussion.
    excerpt = " ".join(str(report.get("vulnerability_information") or "").split()[:100])[:1200]
    return dict(id="h1-" + expected, report_id=expected, source_url=f"https://hackerone.com/reports/{expected}",
                title=str(report.get("title") or "Untitled public report")[:500],
                program=str(team.get("handle") or "Unknown")[:100],
                outcome=str(report.get("substate") or report.get("state") or "unknown").lower()[:80],
                disclosed_at=str(report["disclosed_at"])[:80], severity=str(report.get("severity_rating") or "unknown")[:50],
                weakness=str(weakness.get("name") or "")[:200], bounty_amount=amount,
                currency=str(team.get("default_currency") or "unknown")[:20],
                rewarded=Decimal(amount) > 0 if amount is not None else None, excerpt=excerpt,
                fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                source_hash=hashlib.sha256(json.dumps(report, sort_keys=True).encode()).hexdigest(),
                source_verified=True, eligibility="Historical outcome only; verify current target policy independently")


class Collector:
    def __init__(self):
        self.lock = threading.Lock()
        self.last_fetch = 0

    def fetch(self, identifier):
        identifier = report_id(identifier)
        with self.lock:
            delay = 1 - (time.monotonic() - self.last_fetch)
            if delay > 0:
                time.sleep(delay)
            self.last_fetch = time.monotonic()
            return normalize(read_json(f"https://hackerone.com/reports/{identifier}.json"), identifier)

    @staticmethod
    def configured():
        return bool(environment("H1_API_USERNAME") and environment("H1_API_TOKEN"))

    def discover(self, query="", page=1):
        if not self.configured():
            raise ValueError("Discovery requires KIROSHI_H1_API_USERNAME and KIROSHI_H1_API_TOKEN in the server environment. Importing public URLs needs no API key.")
        if not isinstance(query, str) or len(query) > 400 or any(ord(c) < 32 for c in query):
            raise ValueError("Search query must be at most 400 characters")
        page = int(page)
        if not 1 <= page <= 100:
            raise ValueError("Page must be between 1 and 100")
        query = "disclosed:true" + (f" AND ({query})" if query.strip() else "")
        parameters = urlencode({"queryString": query, "sort": "-disclosed_at", "page[size]": 10, "page[number]": page})
        credentials = f"{environment('H1_API_USERNAME')}:{environment('H1_API_TOKEN')}"
        authorization = "Basic " + base64.b64encode(credentials.encode()).decode()
        with self.lock:
            delay = 1 - (time.monotonic() - self.last_fetch)
            if delay > 0:
                time.sleep(delay)
            self.last_fetch = time.monotonic()
            payload = read_json("https://api.hackerone.com/v1/hackers/hacktivity?" + parameters, authorization)
        results = []
        for row in payload.get("data", [])[:10]:
            attributes = row.get("attributes", {})
            if attributes.get("disclosed") is not True or not attributes.get("disclosed_at"):
                continue
            try:
                identifier = report_id(str(row["id"]))
            except (ValueError, KeyError):
                continue
            results.append(dict(report_id=identifier, title=str(attributes.get("title") or "Public report")[:500],
                                source_url=f"https://hackerone.com/reports/{identifier}",
                                outcome=str(attributes.get("substate") or "unknown"),
                                bounty_amount=attributes.get("total_awarded_amount"), disclosed_at=attributes["disclosed_at"]))
        return dict(results=results, page=page)
