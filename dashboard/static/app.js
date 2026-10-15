"use strict";
let state = {
  engagements: [],
  jobs: [],
  findings: [],
  tools: [],
  sessions: [],
  assets: [],
};
let view = "overview",
  selected = "",
  activeLog = null,
  pollBusy = false;
const $ = (s) => document.querySelector(s);
const esc = (v) =>
  String(v ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const when = (s) =>
  s
    ? new Date(s).toLocaleString([], {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "—";
const pill = (s) =>
  `<span class="pill ${esc(s)}">${esc(s.replaceAll("_", " "))}</span>`;
const pending = (j) => ["queued", "running", "cancelling"].includes(j.status);
const engagementName = (id) =>
  state.engagements.find((e) => e.id === id)?.name || "Engagement";
const filtered = (rows) =>
  selected ? rows.filter((x) => x.engagement_id === selected) : rows;
function toast(text, error = false) {
  const el = $("#toast");
  el.textContent = text;
  el.className = error ? "error" : "";
  el.style.display = "block";
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => (el.style.display = "none"), 6500);
}
async function api(path, body) {
  const response = await fetch(
    "/api/" + path,
    body
      ? {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Hunt-Token": state.token,
          },
          body: JSON.stringify(body),
        }
      : {},
  );
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Request failed");
  return data;
}
async function refresh(renderPage = true) {
  state = await api("state");
  if (renderPage) render();
}
function heading(title, subtitle, action = "") {
  return `<div class="page-heading"><div><div class="eyebrow">ENGAGEMENT CONSOLE</div><h1>${title}</h1><p>${subtitle}</p></div>${action}</div>`;
}
function empty(title, text, action = "") {
  return `<div class="empty"><div class="empty-icon">◎</div><h3>${title}</h3><p>${text}</p>${action}</div>`;
}
function panel(title, content, action = "") {
  return `<section class="panel"><div class="panel-head"><h2>${title}</h2>${action}</div>${content}</section>`;
}
function newButton() {
  return '<button class="btn primary" data-action="new-engagement">＋ New engagement</button>';
}
function engagementFilter() {
  return `<select id="engagement-filter" aria-label="Filter engagement"><option value="">All engagements</option>${state.engagements.map((e) => `<option value="${e.id}" ${e.id === selected ? "selected" : ""}>${esc(e.name)}</option>`).join("")}</select>`;
}
function jobTable(jobs) {
  if (!jobs.length)
    return empty(
      "No jobs yet",
      "Create an engagement, preview a command, then queue your first run.",
    );
  return `<div class="table-wrap"><table><thead><tr><th>Tool / target</th><th>Engagement</th><th>Identity</th><th>Status</th><th>Created</th><th></th></tr></thead><tbody>${jobs.map((j) => `<tr><td><strong class="mono">${esc(j.tool)}</strong><div class="sub path">${esc(j.target)}</div></td><td>${esc(engagementName(j.engagement_id))}</td><td>${esc(j.identity || "Anonymous")}</td><td>${pill(j.status)}</td><td class="text-muted">${when(j.created)}</td><td><button class="btn small" data-action="log" data-id="${j.id}">Logs ↗</button></td></tr>`).join("")}</tbody></table></div>`;
}
function overview() {
  const installed = state.tools.filter((t) => t.installed),
    ready = installed.filter((t) => t.adapter),
    running = state.jobs.filter(pending);
  return (
    heading(
      "Your hunt starts here.",
      "A local command center for your bug bounty engagements.",
      newButton(),
    ) +
    `<div class="stats">${[
      [
        "Engagements",
        state.engagements.length,
        "Explicit scope, isolated workspaces",
        "◎",
      ],
      ["Active jobs", running.length, "One worker · bounded execution", "↗"],
      [
        "Cached assets",
        state.assets.length,
        "Persistent across anonymous & session runs",
        "⌘",
      ],
      [
        "Ready tools",
        ready.length,
        `${installed.length} installed · ${state.tools.length} in catalog`,
        "⚒",
      ],
    ]
      .map(
        ([label, n, caption, icon]) =>
          `<div class="stat"><div class="stat-label">${label}<span class="stat-symbol">${icon}</span></div><div class="stat-value">${n}</div><div class="stat-caption">${caption}</div></div>`,
      )
      .join(
        "",
      )}</div><div class="overview-banner"><div><h2>Recon first. Add a session when you're ready.</h2><p>Your discoveries stay cached. Layer authenticated runs onto the same engagement.</p></div><span class="badge-outline">BUILT FOR WSL</span></div><div class="grid-two"><div>${panel("Recent jobs", jobTable(state.jobs.slice(0, 6)), '<button class="btn small" data-view="jobs">All jobs →</button>')}${panel("Engagements", state.engagements.length ? engagementTable(state.engagements.slice(0, 4)) : empty("Start with a scope", "Add authorized hosts, exclusions and a program policy.", newButton()))}</div><div>${panel(
      "Execution environment",
      `<div class="panel-body"><div class="row spread"><h3>WSL native runner</h3>${pill("ready")}</div><p class="help">Uses your installed Linux binaries. No cloud runner.</p><div class="progress-section">${[
        "Recon",
        "DNS",
        "HTTP",
        "Discovery",
      ]
        .map((category) => {
          let tools = state.tools.filter((t) => t.category === category);
          let count = tools.filter((t) => t.installed).length;
          return `<div class="metric-line"><span>${category}</span><span>${count} / ${tools.length} installed</span></div><progress class="bar" max="${tools.length}" value="${count}"></progress>`;
        })
        .join(
          "",
        )}</div><button class="btn" data-view="tools">Manage toolchain ↗</button></div>`,
    )}${panel("Working model", `<div class="panel-body"><div class="activity-item"><span class="activity-dot"></span><div><h3>01 / Set the boundary</h3><p>Explicit hosts and exclusions. Policy URL stays separate.</p></div></div><div class="activity-item"><span class="activity-dot"></span><div><h3>02 / Collect & cache</h3><p>Anonymous discovery, live job logs and retained evidence.</p></div></div><div class="activity-item"><span class="activity-dot"></span><div><h3>03 / Add context</h3><p>Scoped session headers, named identities and agent handoffs.</p></div></div></div>`)}</div></div><div class="page-bottom">HUNT / LOCAL WORKSPACE · Original scaffold by 0xcucumbersalad · Dashboard extension</div>`
  );
}
function engagementTable(rows) {
  return `<div class="table-wrap"><table><thead><tr><th>Engagement</th><th>Scope</th><th>Budget</th><th></th></tr></thead><tbody>${rows.map((e) => `<tr><td><strong>${esc(e.name)}</strong><div class="sub">${state.sessions.filter((s) => s.engagement_id === e.id).length} saved sessions</div></td><td class="mono">${e.scope.map(esc).join("<br>")}</td><td>${e.rate}/s <span class="text-muted">· ${e.duration}s</span></td><td><button class="btn small" data-action="open-engagement" data-id="${e.id}">Open →</button></td></tr>`).join("")}</tbody></table></div>`;
}
function engagementView() {
  const e = state.engagements.find((x) => x.id === selected);
  if (!e)
    return (
      heading(
        "Engagements",
        "Scope, sessions and execution limits in one place.",
        newButton(),
      ) +
      panel(
        "Your engagements",
        state.engagements.length
          ? engagementTable(state.engagements)
          : empty(
              "No engagements yet",
              "Create a workspace for one authorized program.",
              newButton(),
            ),
      )
    );
  const sessions = state.sessions.filter((s) => s.engagement_id === e.id);
  return (
    heading(
      esc(e.name),
      "Anonymous and authenticated work share the same persistent cache.",
      `<div class="row"><button class="btn" data-action="edit-engagement" data-id="${e.id}">Edit scope</button><button class="btn primary" data-action="run" data-id="${e.id}">＋ New run</button></div>`,
    ) +
    `<div class="grid-two"><div>${panel("Scope & operating limits", `<div class="panel-body stack"><div><label>IN SCOPE</label><code>${e.scope.map(esc).join("<br>")}</code></div><div><label>EXCLUDED</label><code>${e.excluded.map(esc).join("<br>") || "None specified"}</code></div><div><label>PROGRAM POLICY</label><span class="path text-muted">${esc(e.policy) || "Not provided"}</span></div><div class="row"><span class="pill">${e.rate} requests / second</span><span class="pill">${e.duration} second job limit</span><span class="pill">${esc(e.provider)}</span></div></div>`)}${panel("Cached discoveries", assetTable(state.assets.filter((a) => a.engagement_id === e.id).slice(0, 10)), `<button class="btn small" data-view="assets">All assets →</button>`)}${panel("Run history", jobTable(state.jobs.filter((j) => j.engagement_id === e.id).slice(0, 8)))}</div><div>${panel("Session credentials", `<div class="panel-body"><div class="note neutral">Start anonymously. Add cookies or headers here whenever you need an authenticated pass.</div>${sessions.length ? sessions.map((s) => `<div class="session-card"><div class="row spread"><h3>${esc(s.label)}</h3><span class="pill ready">Saved</span></div><p class="path">${esc(s.origin)}</p><code>${s.header_names.map(esc).join(", ")} · values hidden</code><div class="row"><button class="btn small" data-action="replace-session" data-id="${s.id}">Replace</button><button class="btn small danger" data-action="delete-session" data-id="${s.id}">Delete</button></div></div>`).join("") : "<p>No sessions saved. Anonymous runs are ready.</p>"}<div class="form-actions"><button class="btn" data-action="session" data-id="${e.id}">＋ Add session</button></div></div>`)}${panel("Continue with an agent", `<div class="panel-body"><p>Your friend's hunt brief is generated in this engagement workspace. Claude Code and Codex use shared instructions and handoff notes.</p><div class="form-actions"><button class="btn" data-view="agent">Open handoff ↗</button></div></div>`)}</div></div>`
  );
}
function assetTable(rows) {
  if (!rows.length)
    return empty(
      "No cached assets yet",
      "Run discovery or HTTP inventory. Eligible results are normalized here; raw logs are always retained.",
    );
  return `<div class="table-wrap"><table><thead><tr><th>Asset / endpoint</th><th>Source</th><th>Latest identity</th><th>Runs</th><th></th></tr></thead><tbody>${rows.map((a) => `<tr><td class="mono path">${esc(a.value)}</td><td>${esc(a.tool)}</td><td>${esc(a.identity)}</td><td>${a.job_ids.length}</td><td><button class="btn small" data-action="asset-run" data-id="${a.id}">Run on asset ↗</button></td></tr>`).join("")}</tbody></table></div>`;
}
function assetsView() {
  return (
    heading(
      "Asset cache",
      "Persisted discoveries. New sessions never discard earlier recon.",
    ) +
    `<div class="toolbar">${engagementFilter()}<input id="asset-search" placeholder="Filter cached URLs or hosts…" aria-label="Search cached assets"></div>` +
    panel(
      "Discovered assets",
      `<div id="asset-table">${assetTable(filtered(state.assets))}</div>`,
    )
  );
}
function jobsView() {
  return (
    heading(
      "Jobs & logs",
      "Bounded local commands. Every run keeps its identity and evidence.",
      state.engagements.length
        ? '<button class="btn primary" data-action="run">＋ New run</button>'
        : "",
    ) +
    `<div class="toolbar">${engagementFilter()}<span class="text-muted">${state.jobs.filter(pending).length} pending · one worker</span></div>` +
    panel("Execution history", jobTable(filtered(state.jobs)))
  );
}
function findingsView() {
  let rows = filtered(state.findings);
  return (
    heading(
      "Findings",
      "Keep observations separate from validated vulnerabilities.",
      state.engagements.length
        ? '<button class="btn primary" data-action="finding">＋ Add finding</button>'
        : "",
    ) +
    `<div class="toolbar">${engagementFilter()}</div>` +
    panel(
      "Review queue",
      rows.length
        ? `<div class="table-wrap"><table><thead><tr><th>Finding</th><th>Severity</th><th>Status</th><th>Engagement</th><th></th></tr></thead><tbody>${rows.map((f) => `<tr><td><strong>${esc(f.title)}</strong><div class="sub path">${esc(f.target)}</div></td><td>${pill(f.severity)}</td><td>${pill(f.status)}</td><td>${esc(engagementName(f.engagement_id))}</td><td><button class="btn small" data-action="edit-finding" data-id="${f.id}">Review →</button></td></tr>`).join("")}</tbody></table></div>`
        : empty(
            "No findings recorded",
            "Scanner matches begin unverified. Add reproducible evidence before confirming impact.",
          ),
    )
  );
}
function toolsView() {
  return (
    heading(
      "Your WSL toolchain",
      `${state.tools.length} catalog entries. ${state.tools.filter((t) => t.installed && t.adapter).length} installed tools have runnable adapters.`,
    ) +
    `<div class="note neutral">Ready adapters can be launched from an engagement. Inventory-only entries are detected but require an adapter before this dashboard can run them. No tools are installed automatically.</div><div class="toolbar"><input id="tool-search" placeholder="Search tools or categories…" aria-label="Search toolchain"><select id="tool-filter" aria-label="Tool availability"><option value="all">All tools</option><option value="ready">Ready to run</option><option value="installed">Installed</option><option value="missing">Missing</option></select></div><div class="tool-grid" id="tool-grid">${toolCards(state.tools)}</div>`
  );
}
function toolCards(rows) {
  return rows
    .map(
      (t) =>
        `<article class="tool-card"><div class="row spread"><h3>${esc(t.name)}</h3>${pill(t.installed ? (t.adapter ? "ready" : "installed") : "missing")}</div><p>${esc(t.description)}</p><code title="${esc(t.path || "Not found on WSL PATH")}">${esc(t.path || "Not found on WSL PATH")}</code><footer><span>${esc(t.category)} · ${t.adapter ? "Runnable adapter" : "Inventory only"}</span><button class="btn small" data-action="tool-path" data-id="${esc(t.name)}">Path</button></footer></article>`,
    )
    .join("");
}
function agentView() {
  const e =
    state.engagements.find((e) => e.id === selected) || state.engagements[0];
  return (
    heading(
      "Agent handoff",
      "Switch clients while retaining the same scope, evidence and next action.",
    ) +
    (!e
      ? panel(
          "Workspace",
          empty(
            "Create an engagement first",
            "Agent workspaces are generated from your friend’s original hunt script.",
          ),
        )
      : `<div class="toolbar">${engagementFilter()}</div><div class="note neutral">Agent execution stays in your terminal. This page prepares the workspace and launch command; it does not run an unattended AI agent. Your existing Claude Code provider configuration applies.</div><div class="grid-two"><div>${panel("Shared handoff", `<div class="panel-body"><label for="handoff-text">Current position, evidence references, pending cleanup and next action</label><textarea id="handoff-text" rows="15" placeholder="Loading…"></textarea><div class="form-actions"><button class="btn primary" data-action="save-handoff" data-id="${e.id}">Save handoff</button></div></div>`)}</div><div>${panel("Launch locally", `<div class="panel-body stack"><div><label>ENGAGEMENT</label><strong>${esc(e.name)}</strong></div><div><label>TERMINAL COMMAND</label><pre id="agent-command" class="terminal">Loading…</pre></div><button class="btn" data-action="copy-agent">Copy command</button><p class="help">Stop the current agent before launching another. Sessions saved in this dashboard are not automatically injected into an external agent process.</p><div><label>WORKSPACE</label><code id="agent-path" class="path"></code></div></div>`)}</div></div>`)
  );
}
function render() {
  const names = {
    overview: "Overview",
    engagements: "Engagements",
    assets: "Asset cache",
    jobs: "Jobs & logs",
    findings: "Findings",
    tools: "Toolchain",
    agent: "Agent handoff",
  };
  $("#crumb").textContent = names[view];
  document
    .querySelectorAll("#nav button")
    .forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  $("#page").innerHTML = {
    overview,
    engagements: engagementView,
    assets: assetsView,
    jobs: jobsView,
    findings: findingsView,
    tools: toolsView,
    agent: agentView,
  }[view]();
  if (view === "agent" && state.engagements.length)
    loadAgent().catch((e) => toast(e.message, true));
}
function navigate(next) {
  view = next;
  render();
}
function modal(title, intro, contents) {
  activeLog = null;
  $("#modal-content").innerHTML =
    `<button class="dialog-close" data-action="close" aria-label="Close dialog">×</button><h2>${title}</h2><p class="intro">${intro}</p>${contents}`;
  if (!$("#modal").open) $("#modal").showModal();
}
function closeModal() {
  $("#modal").close();
  activeLog = null;
}
function field(label, name, value = "", type = "text", extra = "") {
  return `<div ${extra}><label for="f-${name}">${label}</label><input id="f-${name}" name="${name}" type="${type}" value="${esc(value)}"></div>`;
}
function engagementModal(id) {
  const e = state.engagements.find((x) => x.id === id) || {};
  modal(
    id ? "Edit engagement" : "New engagement",
    "Define the authorized boundary before running tools.",
    `<form id="engagement-form"><input type="hidden" name="id" value="${e.id || ""}"><div class="form-grid">${field("Engagement name", "name", e.name || "")}${field("Program / policy URL", "policy", e.policy || "")}<div><label>In-scope hosts (one per line)</label><textarea name="scope" required placeholder="example.com&#10;*.example.com">${esc((e.scope || []).join("\n"))}</textarea><div class="help">Hostnames/IPs only. A wildcard does not include the apex.</div></div><div><label>Excluded hosts</label><textarea name="excluded" placeholder="payments.example.com">${esc((e.excluded || []).join("\n"))}</textarea></div>${field("Rate limit / second", "rate", e.rate || 5, "number")}${field("Maximum job duration / seconds", "duration", e.duration || 300, "number")}<div><label>Preferred agent client</label><select name="provider"><option value="claude" ${e.provider === "claude" ? "selected" : ""}>Claude Code (your configured provider)</option><option value="codex" ${e.provider === "codex" ? "selected" : ""}>Codex</option></select></div><div><label>Program notes / constraints</label><textarea name="notes">${esc(e.notes || "")}</textarea></div><label class="check-label full"><input name="authorized" type="checkbox" required ${e.authorized ? "checked" : ""}>I have authorization for these assets and have reviewed the program’s testing rules.</label></div><div class="inline-error" id="form-error"></div><div class="form-actions"><button type="button" class="btn" data-action="close">Cancel</button><button class="btn primary">Save engagement</button></div></form>`,
  );
}
function sessionModal(engagementId, sessionId) {
  const s = state.sessions.find((s) => s.id === sessionId) || {};
  const e = state.engagements.find((e) => e.id === engagementId);
  modal(
    sessionId ? "Replace session" : "Add session",
    "Stored locally with restricted file permissions. Values are never returned by the API.",
    `<form id="session-form"><input type="hidden" name="engagement_id" value="${e.id}"><input type="hidden" name="id" value="${s.id || ""}"><div class="form-grid">${field("Identity / session label", "label", s.label || "Account A")}${field("Exact origin (scheme, host, port)", "origin", s.origin || "https://" + (e.scope.find((h) => !h.startsWith("*.")) || ""))}<div class="full"><label>Cookie header value</label><input type="password" name="cookie" autocomplete="off" placeholder="session=…; csrf=…"></div><div class="full"><label>Additional headers (one Name: Value per line)</label><textarea name="headers" autocomplete="off" spellcheck="false" placeholder="Authorization: Bearer …&#10;X-CSRF-Token: …"></textarea><div class="help">Exact-origin binding. Redirects stay disabled. Replacing a session affects future runs only.</div></div></div><div class="inline-error" id="form-error"></div><div class="form-actions"><button type="button" class="btn" data-action="close">Cancel</button><button class="btn primary">Save session</button></div></form>`,
  );
}
function runModal(engagementId, target = "") {
  let e =
    state.engagements.find((e) => e.id === engagementId) ||
    state.engagements.find((e) => e.id === selected) ||
    state.engagements[0];
  if (!e) {
    engagementModal();
    return;
  }
  const ready = state.tools.filter((t) => t.adapter && t.installed);
  modal(
    "New tool run",
    "Preview a bounded command. Existing recon stays cached.",
    `<form id="run-form"><div class="form-grid"><div><label>Engagement</label><select name="engagement_id" id="run-engagement">${state.engagements.map((x) => `<option value="${x.id}" ${x.id === e.id ? "selected" : ""}>${esc(x.name)}</option>`).join("")}</select></div><div><label>Tool / profile</label><select name="tool" id="run-tool">${ready.map((t) => `<option value="${t.name}" ${t.name === "httpx" ? "selected" : ""}>${esc(t.name)} — ${esc(t.description)}</option>`).join("")}</select></div><div class="full"><label>Target host or URL</label><input name="target" required value="${esc(target || "https://" + (e.scope.find((h) => !h.startsWith("*.")) || ""))}" placeholder="https://app.example.com"></div><div class="full"><label>Identity / session</label><select name="auth_id" id="run-session"></select><div class="help">HTTP sessions are sent only to their exact origin. DNS/recon/TLS profiles use Anonymous.</div></div></div><div class="note neutral">Nuclei runs the bundled server-header inventory template. Content discovery uses a small bundled wordlist. Broader templates and wordlists need an adapter extension.</div><div class="preview-box" id="command-preview"></div><div class="inline-error" id="form-error"></div><div class="form-actions"><button type="button" class="btn" data-action="preview">Preview command</button><button class="btn primary" ${ready.length ? "" : "disabled"}>Queue run →</button></div></form>`,
  );
  updateRunSessions();
}
function updateRunSessions() {
  const form = $("#run-form");
  if (!form) return;
  const key = form.elements.engagement_id.value;
  const http = ["httpx", "katana", "feroxbuster", "ffuf", "nuclei"].includes(
    form.elements.tool.value,
  );
  $("#run-session").innerHTML =
    '<option value="">Anonymous</option>' +
    state.sessions
      .filter((s) => s.engagement_id === key && http)
      .map(
        (s) =>
          `<option value="${s.id}">${esc(s.label)} · ${esc(s.origin)}</option>`,
      )
      .join("");
  $("#command-preview").innerHTML = "";
}
function findingModal(id) {
  const f = state.findings.find((f) => f.id === id) || {};
  modal(
    id ? "Review finding" : "Record finding",
    "Capture impact, reproduction steps and evidence references.",
    `<form id="finding-form"><input type="hidden" name="id" value="${f.id || ""}"><div class="form-grid"><div class="full"><label>Engagement</label><select name="engagement_id">${state.engagements
      .filter((e) => !f.id || e.id === f.engagement_id)
      .map(
        (e) =>
          `<option value="${e.id}" ${e.id === (f.engagement_id || selected) ? "selected" : ""}>${esc(e.name)}</option>`,
      )
      .join(
        "",
      )}</select></div>${field("Title", "title", f.title || "")}${field("Affected target", "target", f.target || "")}<div><label>Severity</label><select name="severity">${["info", "low", "medium", "high", "critical"].map((v) => `<option ${v === (f.severity || "info") ? "selected" : ""}>${v}</option>`).join("")}</select></div><div><label>Status</label><select name="status">${["unverified", "confirmed", "dismissed", "reported"].map((v) => `<option ${v === (f.status || "unverified") ? "selected" : ""}>${v}</option>`).join("")}</select></div><div class="full"><label>Evidence and notes (Markdown)</label><textarea name="notes" rows="9">${esc(f.notes || "## Impact\n\n## Reproduction steps\n\n## Evidence\n")}</textarea></div></div><div class="inline-error" id="form-error"></div><div class="form-actions"><button class="btn primary">Save finding</button></div></form>`,
  );
}
async function logModal(id) {
  modal(
    "Job output",
    "Live tail · last 100 KB displayed. Download retains the complete capped log.",
    `<div id="job-meta"></div><pre class="terminal" id="job-output">Loading…</pre>`,
  );
  activeLog = id;
  await updateLog();
}
async function updateLog() {
  if (!activeLog || !$("#modal").open) return;
  const id = activeLog;
  const { job, output } = await api(`jobs/${id}/log`);
  if (activeLog !== id) return;
  $("#job-meta").innerHTML =
    `<div class="log-toolbar"><div class="row"><strong class="mono">${esc(job.tool)}</strong>${pill(job.status)}<span class="text-muted">${esc(job.identity || "Anonymous")}</span></div><div class="row"><a class="btn small" href="/api/jobs/${job.id}/download" download>Download</a><button class="btn small" data-action="rerun" data-id="${job.id}">Run again</button>${pending(job) ? `<button class="btn small danger" data-action="cancel-job" data-id="${job.id}">Cancel job</button>` : ""}</div></div><p class="help path">${esc(job.display)}</p><p class="help">${job.error ? esc(job.error) : "Exit code: " + (job.returncode ?? "pending")}</p>`;
  const pre = $("#job-output");
  const bottom = pre.scrollHeight - pre.scrollTop - pre.clientHeight < 35;
  pre.textContent = output;
  if (bottom) pre.scrollTop = pre.scrollHeight;
}
async function loadAgent() {
  const e =
    state.engagements.find((e) => e.id === selected) || state.engagements[0];
  const a = await api("agent/" + e.id);
  if (view !== "agent") return;
  $("#handoff-text").value = a.handoff;
  $("#agent-command").textContent = a.command;
  $("#agent-path").textContent = a.workspace;
}
document.addEventListener("click", async (event) => {
  const el = event.target.closest("[data-action],[data-view]");
  if (!el) return;
  try {
    if (el.dataset.view) {
      navigate(el.dataset.view);
      return;
    }
    const id = el.dataset.id;
    switch (el.dataset.action) {
      case "close":
        closeModal();
        break;
      case "new-engagement":
        engagementModal();
        break;
      case "edit-engagement":
        engagementModal(id);
        break;
      case "open-engagement":
        selected = id;
        navigate("engagements");
        break;
      case "run":
        runModal(id);
        break;
      case "asset-run": {
        const a = state.assets.find((a) => a.id === id);
        runModal(a.engagement_id, a.value);
        break;
      }
      case "rerun": {
        const j = state.jobs.find((j) => j.id === id);
        runModal(j.engagement_id, j.target);
        break;
      }
      case "session":
        sessionModal(id);
        break;
      case "replace-session": {
        const s = state.sessions.find((s) => s.id === id);
        sessionModal(s.engagement_id, id);
        break;
      }
      case "delete-session":
        await api("sessions/delete", { id });
        await refresh();
        toast("Session deleted. Queued jobs retain their own snapshots.");
        break;
      case "preview": {
        const data = Object.fromEntries(new FormData($("#run-form")));
        const p = await api("jobs/preview", data);
        $("#command-preview").innerHTML =
          `<label>COMMAND PREVIEW · ${esc(p.identity)} · ${p.duration}s limit</label><pre class="terminal">${esc(p.display)}</pre><p class="help">${esc(p.auth_notice)}</p>`;
        break;
      }
      case "log":
        await logModal(id);
        break;
      case "cancel-job":
        await api("jobs/cancel", { id });
        await refresh(false);
        await updateLog();
        toast("Cancellation requested");
        break;
      case "finding":
        findingModal();
        break;
      case "edit-finding":
        findingModal(id);
        break;
      case "tool-path": {
        const tool = state.tools.find((t) => t.name === id);
        modal(
          "Configure " + esc(id),
          "Use an absolute path to an existing WSL executable.",
          `<form id="path-form"><input type="hidden" name="tool" value="${esc(id)}">${field("Executable path", "path", tool.path || "")}<div class="inline-error" id="form-error"></div><div class="form-actions"><button class="btn primary">Save executable path</button></div></form>`,
        );
        break;
      }
      case "save-handoff":
        await api("handoff", {
          engagement_id: id,
          text: $("#handoff-text").value,
        });
        toast("Handoff saved");
        break;
      case "copy-agent":
        await navigator.clipboard.writeText($("#agent-command").textContent);
        toast("Launch command copied");
        break;
    }
  } catch (error) {
    if ($("#form-error")) $("#form-error").textContent = error.message;
    else toast(error.message, true);
  }
});
document.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.target;
  const data = Object.fromEntries(new FormData(form));
  try {
    if (form.getAttribute("id") === "engagement-form") {
      data.authorized = form.elements.authorized.checked;
      if (!data.id) delete data.id;
      const e = await api("engagements", data);
      selected = e.id;
      view = "engagements";
    } else if (form.getAttribute("id") === "session-form") {
      if (!data.id) delete data.id;
      await api("sessions", data);
      form.reset();
    } else if (form.getAttribute("id") === "run-form") {
      await api("jobs", data);
      view = "jobs";
      selected = data.engagement_id;
    } else if (form.getAttribute("id") === "finding-form") {
      if (!data.id) delete data.id;
      await api("findings", data);
    } else if (form.getAttribute("id") === "path-form") {
      const paths = Object.fromEntries(
        state.tools.filter((t) => t.path).map((t) => [t.name, t.path]),
      );
      paths[data.tool] = data.path;
      await api("settings", { paths });
    } else return;
    closeModal();
    await refresh();
    toast("Saved locally");
  } catch (error) {
    $("#form-error").textContent = error.message;
  }
});
document.addEventListener("change", (event) => {
  if (event.target.id === "engagement-filter") {
    selected = event.target.value;
    render();
  }
  if (["run-engagement", "run-tool"].includes(event.target.id))
    updateRunSessions();
  if (event.target.id === "tool-filter") filterTools();
});
document.addEventListener("input", (event) => {
  if (event.target.id === "asset-search")
    $("#asset-table").innerHTML = assetTable(
      filtered(state.assets).filter((a) =>
        a.value.toLowerCase().includes(event.target.value.toLowerCase()),
      ),
    );
  if (event.target.id === "tool-search") filterTools();
});
function filterTools() {
  const query = $("#tool-search").value.toLowerCase(),
    filter = $("#tool-filter").value;
  $("#tool-grid").innerHTML = toolCards(
    state.tools.filter(
      (t) =>
        (t.name + " " + t.category + " " + t.description)
          .toLowerCase()
          .includes(query) &&
        (filter === "all" ||
          (filter === "ready" && t.installed && t.adapter) ||
          (filter === "installed" && t.installed) ||
          (filter === "missing" && !t.installed)),
    ),
  );
}
$("#refresh").addEventListener("click", () =>
  refresh().catch((e) => toast(e.message, true)),
);
$("#modal").addEventListener("close", () => (activeLog = null));
setInterval(async () => {
  if (pollBusy) return;
  pollBusy = true;
  try {
    if (activeLog) await updateLog();
    if (state.jobs.some(pending)) {
      await refresh(false);
      if (!$("#modal").open && ["overview", "jobs"].includes(view)) render();
    }
  } catch (error) {
    toast(error.message, true);
  } finally {
    pollBusy = false;
  }
}, 2000);
refresh().catch((error) => toast(error.message, true));
