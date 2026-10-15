"""Transparent evidence-completeness rules, not a prediction of bounty eligibility."""
from datetime import datetime, timezone
import hashlib
import json
import re

from .tools import target_url

FIELDS = {
    "policy_basis": "Current policy clause covering the asset and vulnerability class",
    "prerequisites": "Attacker prerequisites and owned test identities",
    "steps": "Repeatable reproduction steps",
    "request_response": "Sanitized request/response evidence or local evidence references",
    "controls": "Authorized/unauthorized or baseline control comparison",
    "boundary": "Expected permission and the observed security boundary violation",
    "impact": "Concrete demonstrated impact and affected owned test objects",
    "false_positive_checks": "Caching, public data, expected permissions and scanner checks",
    "duplicate_search": "Public disclosure / known-issue search and its limits",
    "severity_basis": "Severity reasoning, prerequisites and demonstrated impact limits",
    "remediation": "Suggested remediation",
}
NOTICE = ("Evidence completeness and reviewer attestations only. This does not independently "
          "replay requests, verify claims, predict HackerOne disposition, establish bounty eligibility, "
          "or detect undisclosed duplicates. Public report rewards never override current policy.")


def content_hash(finding, engagement):
    values = {k: finding.get(k, "") for k in ("title", "target", "severity", "notes")}
    values["policy"] = {k: engagement.get(k) for k in ("policy", "scope", "excluded", "notes")}
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def normalize_review(value):
    if not isinstance(value, dict):
        raise ValueError("Review must be a JSON object")
    result = {name: str(value.get(name, ""))[:6000].strip() for name in FIELDS}
    for key, choices, default in (
        ("eligibility", ("unknown", "eligible", "excluded"), "unknown"),
        ("impact_assessment", ("unknown", "demonstrated", "informational", "expected_behavior"), "unknown"),
        ("false_positive_assessment", ("unknown", "ruled_out", "identified"), "unknown"),
    ):
        result[key] = value.get(key, default)
        if result[key] not in choices:
            raise ValueError(f"Invalid {key}")
    try:
        attempts = int(value.get("reproduction_attempts", 0))
    except (ValueError, TypeError):
        raise ValueError("Reproduction attempts must be a number") from None
    if not 0 <= attempts <= 100:
        raise ValueError("Reproduction attempts must be between 0 and 100")
    result.update(reproduction_attempts=attempts, policy_checked_at=str(value.get("policy_checked_at", ""))[:10],
                  reviewer=str(value.get("reviewer", ""))[:100].strip(), attested=value.get("attested") is True)
    refs = value.get("reference_ids", [])
    if not isinstance(refs, list) or len(refs) > 20 or any(not isinstance(r, str) for r in refs):
        raise ValueError("Select at most 20 public references")
    result["reference_ids"] = list(dict.fromkeys(refs))
    return result


def evaluate(finding, engagement, today=None):
    review = finding.get("review") or {}
    checks = []

    def add(key, label, ok, reason):
        checks.append(dict(key=key, label=label, passed=bool(ok), reason=reason))

    try:
        target_url(finding.get("target", ""), engagement)
        in_scope = True
    except ValueError:
        in_scope = False
    add("scope", "Target is explicitly in scope", in_scope, "Checked against current engagement host rules")
    current = today or datetime.now(timezone.utc).date()
    try:
        checked = datetime.strptime(review.get("policy_checked_at", ""), "%Y-%m-%d").date()
        fresh = 0 <= (current - checked).days <= 30
    except (ValueError, TypeError):
        fresh = False
    add("policy_date", "Policy reviewed within 30 days", fresh, "Review the policy again when it changes; 30 days is a local reminder, not a platform rule")
    add("eligibility", "Reviewer checked program eligibility", review.get("eligibility") == "eligible" and bool(engagement.get("policy")),
        "Requires a policy URL, accepted asset/class assessment and policy clause evidence")
    for name, label in FIELDS.items():
        text = str(review.get(name, "")).strip()
        placeholder = text.lower() in ("not applicable", "n/a", "todo", "unknown", "none", "not yet tested")
        add(name, label, len(text) >= 20 and not placeholder, "Provide specific evidence or reasoning (at least 20 characters); text length alone does not prove validity")
    add("reproduction", "Reproduced at least twice", review.get("reproduction_attempts", 0) >= 2,
        "Reviewer records independent reproductions, not a tool request count")
    add("demonstrated", "Impact is demonstrated", review.get("impact_assessment") == "demonstrated",
        "Expected behavior and informational observations do not demonstrate a security boundary violation")
    add("false_positives", "False-positive alternatives addressed", review.get("false_positive_assessment") == "ruled_out",
        "Reviewer must explicitly address alternative explanations using control evidence")
    bound = review.get("content_hash") == content_hash(finding, engagement)
    add("attestation", "Named reviewer attests to this evidence", review.get("attested") is True and bool(review.get("reviewer")) and bound,
        "Changing finding content, scope or policy invalidates the prior attestation")
    failed = [c for c in checks if not c["passed"]]
    if not in_scope or review.get("eligibility") == "excluded" or review.get("impact_assessment") == "expected_behavior" or review.get("false_positive_assessment") == "identified":
        disposition = "likely_excluded_or_expected"
    elif review.get("impact_assessment") == "informational":
        disposition = "likely_informational"
    elif failed:
        disposition = "needs_evidence"
    else:
        disposition = "ready_for_human_review"
    return dict(disposition=disposition, ready=not failed, checks=checks, gaps=[c["label"] for c in failed],
                completed=len(checks) - len(failed), total=len(checks), notice=NOTICE)


def related(finding, references):
    """Explainable lexical retrieval; never used to increase readiness or severity."""
    review = finding.get("review") or {}
    explicit = set(review.get("reference_ids", []))
    tokens = set(re.findall(r"[a-z0-9]{3,}", (finding.get("title", "") + " " + review.get("boundary", "")).lower()))
    tokens -= {"the", "and", "for", "with", "from", "this", "that", "can", "user", "report"}
    results = []
    for ref in references:
        terms = set(re.findall(r"[a-z0-9]{3,}", (ref.get("title", "") + " " + ref.get("weakness", "")).lower()))
        overlap = sorted(tokens & terms)
        if ref["id"] not in explicit and len(overlap) < 2:
            continue
        results.append({**ref, "match_terms": overlap, "linked": ref["id"] in explicit,
                        "match_score": len(overlap) + (100 if ref["id"] in explicit else 0)})
    return sorted(results, key=lambda r: (-r["match_score"], r["id"]))[:8]
