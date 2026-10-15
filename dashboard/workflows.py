"""Bounded sequential workflows built from the existing scoped job adapters."""
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import secrets
from urllib.parse import urlsplit
import uuid

from .tools import allowed, passive_seed, target_url
from .traffic import HTTP_TOOLS


ACTIVE = {"queued", "running"}


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stages(discovery):
    return [
        ("subfinder", "Subdomain discovery", "passive"),
        ("dnsx", "Resolve scoped hosts", "hosts"),
        ("httpx", "HTTP after host discovery", "urls"),
        ("tlsx", "TLS inventory", "hosts"),
        ("urlfinder", "Find archived URLs", "passive"),
        ("httpx", "HTTP after URL discovery", "urls"),
        ("katana", "Crawl responding origins", "origins"),
        ("httpx", "HTTP after crawling", "urls"),
        (discovery, "Discover paths on responding origins", "origins"),
        ("httpx", "HTTP after path discovery", "urls"),
        ("nuclei", "Server-header inventory", "live_urls"),
    ]


class WorkflowMixin:
    def stage_target(self, workflow, stage, position):
        if "targets" in stage:  # Checkpoints created by older versions.
            return stage["targets"][position] if 0 <= position < len(stage["targets"]) else None
        with self.lock:
            row = self.db.execute("SELECT target FROM workflow_targets WHERE workflow_id=? AND stage_index=? AND position=?", (workflow["id"], workflow["stage_index"], position)).fetchone()
        return row[0] if row else None

    def workflow_targets(self, engagement, source):
        self.sync_asset_index()
        with self.lock:
            if source in ("hosts", "passive"):
                assets = self.db.execute("SELECT DISTINCT host,NULL FROM asset_index WHERE engagement_id=? AND host<>''", (engagement["id"],)).fetchall()
            else:
                responding = " AND (status BETWEEN 200 AND 399 OR status IN (401,403))" if source in ("origins", "live_urls") else ""
                assets = self.db.execute("SELECT value,status FROM asset_index WHERE engagement_id=?" + responding + " ORDER BY updated DESC,id", (engagement["id"],)).fetchall()
        names, urls, live = [], [], []
        for rule in engagement["scope"]:
            if "*." in rule:
                continue
            try:
                url, name, _ = target_url(rule, engagement)
                if not allowed(name, engagement):
                    continue
                names.append(name)
                urls.append(url)
            except ValueError:
                continue
        for value, code in assets:
            try:
                url, name, _ = target_url(value, engagement)
                if not allowed(name, engagement):
                    continue
                names.append(name)
                urls.append(url)
                if code and (200 <= code < 400 or code in (401, 403)):
                    live.append(url)
            except ValueError:
                continue
        if source == "passive":
            names += [r[2:] for r in engagement["scope"] if r.startswith("*.") and passive_seed(r[2:], engagement)]
            result = []
            for name in names:
                try:
                    ipaddress.ip_address(name)
                except ValueError:
                    result.append(name)
            return list(dict.fromkeys(result))
        if source == "hosts":
            return list(dict.fromkeys(names))
        if source == "origins":
            return list(dict.fromkeys(urlsplit(u)._replace(path="/", query="", fragment="").geturl() for u in live))
        if source == "live_urls":
            return list(dict.fromkeys(live))
        # Probe HTTPS and HTTP for scoped hosts, plus exact discovered URL paths.
        for name in names:
            authority = f"[{name}]" if ":" in name else name
            urls.extend((f"https://{authority}/", f"http://{authority}/"))
        return list(dict.fromkeys(urls))

    def workflow_plan(self, payload):
        engagement = self.get("engagement", payload.get("engagement_id"))
        discovery = payload.get("discovery", "ffuf")
        if discovery not in ("ffuf", "feroxbuster"):
            raise ValueError("Choose ffuf or feroxbuster for path discovery")
        def optional_limit(name):
            value = payload.get(name)
            if value is None or value == "":
                return None
            if isinstance(value, bool) or not str(value).isascii() or not str(value).isdigit():
                raise ValueError("Job and target limits must be whole numbers; leave blank or use 0 for unlimited")
            return int(value) or None
        maximum, target_limit = optional_limit("max_jobs"), optional_limit("max_targets")
        available = {t["name"]: bool(t.get("runnable", t["installed"] and t["adapter"])) for t in self.tools()}
        auth_id = payload.get("auth_id") or None
        auth = self.get("auth", auth_id) if auth_id else None
        if auth and auth["engagement_id"] != engagement["id"]:
            raise ValueError("Session belongs to another engagement")
        plan = dict(engagement_id=engagement["id"], discovery=discovery, max_jobs=maximum, max_targets=target_limit,
                    allow_repeat=payload.get("allow_repeat") is True, auth_id=auth_id,
                    auth_revision=auth.get("revision", auth["updated"]) if auth else None,
                    scope_hash=hashlib.sha256(json.dumps(engagement, sort_keys=True).encode()).hexdigest(),
                    stages=[dict(tool=t, title=title, source=source, available=available.get(t, False)) for t, title, source in stages(discovery)],
                    initial_hosts=len(self.workflow_targets(engagement, "hosts")),
                    passive_seeds=len(self.workflow_targets(engagement, "passive")))
        if not plan["initial_hosts"] and not plan["passive_seeds"]:
            raise ValueError("No executable host scope or passive wildcard seeds; URL-only scope cannot be scanned")
        if not any(s["available"] for s in plan["stages"]):
            raise ValueError("No workflow tools are ready; configure Toolchain first")
        token = hashlib.sha256((self.token + json.dumps(plan, sort_keys=True)).encode()).hexdigest()
        return {**plan, "plan_token": token,
                "notice": "Stages run in order, one process at a time. Later HTTP stages probe newly discovered URLs. Identical completed probes reuse cache. Missing tools and target/job limits are reported. No AI or broad vulnerability templates run automatically."}

    def start_workflow(self, payload):
        with self.lock:
            plan = self.workflow_plan(payload)
            if not secrets.compare_digest(str(payload.get("plan_token", "")), plan["plan_token"]):
                raise ValueError("Preview the current workflow before starting it")
            if any(w["engagement_id"] == plan["engagement_id"] and w["status"] in ACTIVE for w in self.all("workflow")):
                raise ValueError("This engagement already has an active workflow")
            workflow = {**plan, "id": uuid.uuid4().hex[:16], "status": "queued", "created": stamp(),
                        "stage_index": 0, "job_ids": [], "seen": [], "activity": [], "limited": False}
            self.activity(workflow, "queued", "Workflow queued; stages will execute sequentially")
            return self.put("workflow", workflow)

    @staticmethod
    def workflow_view(workflow):
        # Keep polling small even when a stage has thousands of candidate URLs.
        result = {k: v for k, v in workflow.items() if k not in ("seen", "plan_token", "scope_hash")}
        result["stages"] = [{k: v for k, v in stage.items() if k != "targets"} for stage in workflow["stages"]]
        return result

    def cancel_workflow(self, key):
        with self.lock:
            workflow = self.get("workflow", key)
            if workflow["status"] not in ACTIVE:
                return workflow
            if workflow.get("active_job"):
                self.cancel(workflow["active_job"])
            workflow.update(status="cancelled", finished=stamp())
            self.activity(workflow, "cancelled", "Workflow cancelled; no further tools will be queued")
            self.put("workflow", workflow)
            self.notify_result("workflow", workflow)
            return workflow

    def resume_workflow(self, key):
        """Resume a stopped checkpoint without replaying completed stages."""
        with self.lock:
            workflow = self.get("workflow", key)
            if workflow["status"] not in ("failed", "cancelled", "interrupted", "blocked", "rate_limited", "timed_out"):
                raise ValueError("Only a stopped workflow can be resumed")
            engagement = self.get("engagement", workflow["engagement_id"])
            current_hash = hashlib.sha256(json.dumps(engagement, sort_keys=True).encode()).hexdigest()
            if current_hash != workflow.get("scope_hash"):
                raise ValueError("Engagement scope or settings changed; preview a new workflow")
            if workflow.get("auth_id"):
                auth = self.get("auth", workflow["auth_id"])
                if auth.get("revision", auth["updated"]) != workflow["auth_revision"]:
                    raise ValueError("Session changed; preview a new workflow")
            if any(w["engagement_id"] == engagement["id"] and w["status"] in ACTIVE for w in self.all("workflow")):
                raise ValueError("This engagement already has an active workflow")
            if any(j.get("workflow_id") == key and j["status"] in ("queued", "running", "cancelling") for j in self.all("job")):
                raise ValueError("Wait for the previous tool process to stop before resuming")
            if workflow["stage_index"] >= len(workflow["stages"]) or (workflow.get("max_jobs") and len(workflow["job_ids"]) >= workflow["max_jobs"]):
                raise ValueError("Workflow run limit reached; preview a new workflow")
            stage = workflow["stages"][workflow["stage_index"]]
            tools = {t["name"]: t.get("runnable", t.get("installed") and t.get("adapter")) for t in self.tools()}
            if not tools.get(stage["tool"]):
                raise ValueError(f"Install or configure {stage['tool']} before resuming")
            candidate = workflow.get("stopped_job") or workflow.get("active_job") or (workflow["job_ids"][-1] if workflow["job_ids"] else None)
            job = self.get("job", candidate) if candidate else None
            if job and job.get("workflow_id") != key:
                raise ValueError("Workflow checkpoint belongs to another workflow")
            retry = job and job.get("workflow_stage") == workflow["stage_index"] + 1 and (job["status"] != "completed" or job.get("processing_error"))
            if retry or workflow.get("pending_target"):
                target = job["target"] if retry else workflow["pending_target"]
                cursor = stage.get("cursor", 0)
                if not cursor or self.stage_target(workflow, stage, cursor - 1) != target:
                    raise ValueError("Workflow checkpoint is incomplete; preview a new workflow")
                if workflow.get("max_targets") and stage.get("launched", 0) >= workflow["max_targets"]:
                    raise ValueError("Stage run limit reached; preview a new workflow")
                stage["cursor"] -= 1
                if retry:
                    run_key = self.historical_run_key(job)
                    workflow["seen"] = [seen for seen in workflow["seen"] if seen != run_key]
                workflow["retry_target"] = target
            for remaining in workflow["stages"][workflow["stage_index"]:]:
                remaining["available"] = bool(tools.get(remaining["tool"]))
            workflow.update(status="queued", active_job=None, error=None, resumed=stamp(), resume_count=workflow.get("resume_count", 0) + 1)
            for field in ("finished", "stopped_job", "pending_target"):
                workflow.pop(field, None)
            self.activity(workflow, "resumed", f"Resuming stage {workflow['stage_index'] + 1}; completed stages remain cached and original run limits still apply")
            return self.put("workflow", workflow)

    def advance_workflows(self):
        with self.lock:
            for workflow in self.all("workflow"):
                if workflow["status"] not in ACTIVE:
                    continue
                try:
                    self.advance_workflow(workflow)
                except Exception as exc:
                    workflow.update(status="failed", finished=stamp(), error=str(exc))
                    self.activity(workflow, "failed", "Workflow stopped; review its error before restarting")
                    self.put("workflow", workflow)
                    self.notify_result("workflow", workflow)

    def advance_workflow(self, workflow):
        engagement = self.get("engagement", workflow["engagement_id"])
        auth = self.get("auth", workflow["auth_id"]) if workflow["auth_id"] else None
        if auth and auth.get("revision", auth["updated"]) != workflow["auth_revision"]:
            raise ValueError("The workflow session changed; review credentials and start a new workflow")
        workflow["status"] = "running"
        if workflow.get("active_job"):
            job = self.get("job", workflow["active_job"])
            if job["status"] in ("queued", "running", "cancelling"):
                return
            workflow["active_job"] = None
            if job["status"] != "completed" or job.get("processing_error"):
                workflow["stopped_job"] = job["id"]
                outcome = "blocked" if job["status"] in ("blocked", "rate_limited") else job["status"] if job["status"] in ("cancelled", "interrupted") else "failed"
                workflow.update(status=outcome, finished=stamp(),
                                error=f"Stage {workflow['stage_index'] + 1}: {job['tool']} stopped with {job['status']} (exit {job.get('returncode')}, job {job['id']}); review its log before continuing")
                self.activity(workflow, workflow["status"], workflow["error"])
                self.put("workflow", workflow)
                self.notify_result("workflow", workflow)
                return
        # Bound scheduler work even when many targets reuse cached results.
        for _ in range(32):
            if workflow["stage_index"] >= len(workflow["stages"]):
                workflow.update(status="completed_limited" if workflow["limited"] else "completed", finished=stamp())
                self.activity(workflow, workflow["status"], "Workflow ended; review stage coverage and observations. This does not establish a vulnerability.")
                break
            stage = workflow["stages"][workflow["stage_index"]]
            if "targets" in stage:  # Move legacy candidate arrays out of workflow JSON.
                targets = stage.pop("targets")
                self.db.executemany("INSERT OR REPLACE INTO workflow_targets VALUES (?,?,?,?)", ((workflow["id"], workflow["stage_index"], i, t) for i, t in enumerate(targets)))
                stage["target_count"] = len(targets)
            if "target_count" not in stage:
                self.activity(workflow, "stage", f"Stage {workflow['stage_index'] + 1}: {stage['title']} ({stage['tool']})")
                targets = self.workflow_targets(engagement, stage["source"]) if stage["available"] else []
                self.db.executemany("INSERT OR REPLACE INTO workflow_targets VALUES (?,?,?,?)", ((workflow["id"], workflow["stage_index"], i, t) for i, t in enumerate(targets)))
                stage.update(target_count=len(targets), cursor=0, skipped=0, launched=0)
                if not stage["available"]:
                    workflow["limited"] = True
                    stage["reason"] = "Tool unavailable; stage skipped"
                elif not targets:
                    stage["reason"] = "No eligible targets from scope or cached observations"
                if stage.get("reason"):
                    self.activity(workflow, "skipped", stage["reason"])
            if stage["cursor"] >= stage["target_count"]:
                stage["status"] = "skipped" if stage.get("reason") else "limited" if stage.get("candidate_limit") else "completed"
                stage.pop("targets", None)
                workflow["stage_index"] += 1
                continue
            target = self.stage_target(workflow, stage, stage["cursor"])
            if target is None:
                raise ValueError("Workflow target checkpoint is missing; preview a new workflow")
            stage["cursor"] += 1
            payload = dict(engagement_id=engagement["id"], tool=stage["tool"], target=target,
                           diagnostics=True, allow_repeat=workflow["allow_repeat"] or workflow.get("retry_target") == target)
            if auth and stage["tool"] in HTTP_TOOLS:
                parsed, bound = urlsplit(target), urlsplit(auth["origin"])
                if (parsed.scheme, parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80)) == (bound.scheme, bound.hostname, bound.port or (443 if bound.scheme == "https" else 80)):
                    payload["auth_id"] = auth["id"]
            run_key = self.run_key(payload)
            completed = self.has_completed_run(run_key)
            old_jobs = self.matching_jobs(run_key)
            completed = completed or any(j["status"] == "completed" for j in old_jobs)
            if run_key in workflow["seen"] or (completed and not payload["allow_repeat"]):
                stage["skipped"] += 1
                self.activity(workflow, "cached", f"Reused {stage['tool']} result for {target}; no duplicate request")
                continue
            if any(j["status"] in ("queued", "running", "cancelling") for j in old_jobs):
                stage["cursor"] -= 1
                break  # Wait for the existing job, then reuse its results.
            if workflow.get("max_jobs") and len(workflow["job_ids"]) >= workflow["max_jobs"]:
                workflow.update(status="completed_limited", limited=True, finished=stamp())
                self.activity(workflow, "limited", "Total job limit reached; remaining targets/stages were not executed")
                break
            if workflow.get("max_targets") and stage["launched"] >= workflow["max_targets"]:
                stage.update(reason="Stage target limit reached; remaining targets were not executed", status="limited")
                workflow["limited"] = True
                self.activity(workflow, "limited", stage["reason"])
                stage.pop("targets", None)
                workflow["stage_index"] += 1
                continue
            if self.pending_job_count() >= 20:
                stage["cursor"] -= 1
                break
            workflow["pending_target"] = target
            job = self.enqueue(payload)
            workflow.pop("pending_target", None)
            workflow.pop("retry_target", None)
            job.update(workflow_id=workflow["id"], workflow_stage=workflow["stage_index"] + 1, stage_title=stage["title"])
            for event in job.get("activity", []):
                if event["phase"] == "queued":
                    event["message"] = f"Queued {job['tool']} for workflow stage {job['workflow_stage']}: {stage['title']}"
            self.put("job", job)
            workflow["active_job"] = job["id"]
            workflow["job_ids"].append(job["id"])
            workflow["seen"].append(run_key)
            stage["launched"] += 1
            self.activity(workflow, "running", f"{stage['tool']} → {target}")
            break
        self.put("workflow", workflow)
        if workflow["status"] not in ACTIVE:
            self.notify_result("workflow", workflow)
