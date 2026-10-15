"use strict";
let state = {
  engagements: [],
  jobs: [],
  findings: [],
  tools: [],
  sessions: [],
  assets: [],
  references: [],
  review_fields: {},
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
  `<span class="pill ${esc(s)}">${esc(s === "completed" ? "finished" : s.replaceAll("_", " "))}</span>`;
const pending = (j) => ["queued", "running", "cancelling"].includes(j.status);
const toolReady = (t) => t.runnable ?? (t.adapter && t.installed);
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
            "X-Kiroshi-Token": state.token,
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
  return `<div class="table-wrap"><table><thead><tr><th>Tool / target</th><th>Engagement</th><th>Identity</th><th>Status</th><th>Created</th><th></th></tr></thead><tbody>${jobs.map((j) => `<tr><td><strong class="mono">${esc(j.tool)}</strong><div class="sub path">${esc(j.target)}</div></td><td>${esc(engagementName(j.engagement_id))}</td><td>${esc(j.identity || "Anonymous")}</td><td>${pill(j.status)}${j.result_summary ? `<div class="sub">${esc(j.result_summary)}</div>` : ""}${j.waiting_for ? `<div class="sub">${j.manual_hold ? "Manual traffic hold" : "Waiting for cooldown"}</div>` : ""}</td><td class="text-muted">${when(j.created)}</td><td><button class="btn small" data-action="log" data-id="${j.id}">Logs ↗</button></td></tr>`).join("")}</tbody></table></div>`;
}
function overview() {
  const installed = state.tools.filter((t) => t.installed),
    ready = installed.filter((t) => t.adapter),
    running = state.jobs.filter(pending);
  return (
    heading(
      "Your next finding starts here.",
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
    )}${panel("Working model", `<div class="panel-body"><div class="activity-item"><span class="activity-dot"></span><div><h3>01 / Set the boundary</h3><p>Explicit hosts and exclusions. Policy URL stays separate.</p></div></div><div class="activity-item"><span class="activity-dot"></span><div><h3>02 / Collect & cache</h3><p>Anonymous discovery, live job logs and retained evidence.</p></div></div><div class="activity-item"><span class="activity-dot"></span><div><h3>03 / Add context</h3><p>Scoped session headers, named identities and agent handoffs.</p></div></div></div>`)}</div></div><div class="page-bottom">KIROSHI / LOCAL WORKSPACE · Original scaffold by 0xcucumbersalad · Dashboard extension</div>`
  );
}
function engagementTable(rows) {
  return `<div class="table-wrap"><table><thead><tr><th>Engagement</th><th>Scope</th><th>Run limits</th><th></th></tr></thead><tbody>${rows.map((e) => `<tr><td><strong>${esc(e.name)}</strong><div class="sub">${state.sessions.filter((s) => s.engagement_id === e.id).length} saved sessions</div></td><td class="mono">${e.scope.map(esc).join("<br>")}</td><td>${e.rate}/s <span class="text-muted">· ${e.duration}s</span></td><td><button class="btn small" data-action="open-engagement" data-id="${e.id}">Open →</button></td></tr>`).join("")}</tbody></table></div>`;
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
    `<div class="grid-two"><div>${panel("Scope & operating limits", `<div class="panel-body stack"><div><label>IN SCOPE</label><code>${e.scope.map(esc).join("<br>")}</code></div><div><label>EXCLUDED</label><code>${e.excluded.map(esc).join("<br>") || "None specified"}</code></div><div><label>PROGRAM POLICY</label><span class="path text-muted">${esc(e.policy) || "Not provided"}</span></div><div class="row"><span class="pill">${e.rate} requests / second</span><span class="pill">${e.duration} second job limit</span><span class="pill">${esc(e.provider)}</span></div></div>`)}${panel("Cached discoveries", assetTable(state.assets.filter((a) => a.engagement_id === e.id).slice(0, 10)), `<button class="btn small" data-view="assets">All assets →</button>`)}${panel("Run history", jobTable(state.jobs.filter((j) => j.engagement_id === e.id).slice(0, 8)))}</div><div>${panel("Session credentials", `<div class="panel-body"><div class="note neutral">Start anonymously. Add cookies or headers here whenever you need an authenticated pass.</div>${sessions.length ? sessions.map((s) => `<div class="session-card"><div class="row spread"><h3>${esc(s.label)}</h3><span class="pill ready">Saved</span></div><p class="path">${esc(s.origin)}</p><code>${s.header_names.map(esc).join(", ")} · values hidden</code><div class="row"><button class="btn small" data-action="replace-session" data-id="${s.id}">Replace</button><button class="btn small danger" data-action="delete-session" data-id="${s.id}">Delete</button></div></div>`).join("") : "<p>No sessions saved. Anonymous runs are ready.</p>"}<div class="form-actions"><button class="btn" data-action="session" data-id="${e.id}">＋ Add session</button></div></div>`)}${panel("Continue with an agent", `<div class="panel-body"><p>The scaffold script generates a brief in this engagement workspace. Claude Code and Codex use shared instructions and handoff notes.</p><div class="form-actions"><button class="btn" data-view="agent">Open handoff ↗</button></div></div>`)}</div></div>`
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
      "Finished means the tool exited successfully. Review observations; it does not mean a vulnerability was found.",
      state.engagements.length
        ? '<button class="btn primary" data-action="run">＋ New run</button>'
        : "",
    ) +
    `<div class="toolbar">${engagementFilter()}<span class="text-muted">${state.jobs.filter(pending).length} pending · one worker</span></div>` +
    trafficHolds() +
    panel("Execution history", jobTable(filtered(state.jobs)))
  );
}
function trafficHolds() {
  const holds = filtered(state.traffic_gates || []);
  if (!holds.length) return "";
  return panel(
    "Traffic cooldowns",
    `<div class="panel-body stack">${holds.map((g) => `<div class="session-card"><div class="row spread"><strong class="mono path">${esc(g.origin)}</strong>${pill("rate_limited")}</div><p>Observed HTTP ${g.status_code} · ${g.manual_hold ? "Manual hold: server requested a long wait" : "Queued runs wait until " + new Date(g.until * 1000).toLocaleString()}</p><p class="help">This signal does not establish that a WAF caused the response. The stopped job will not automatically retry.</p><button class="btn small" data-action="clear-traffic" data-id="${g.id}">Review hold</button></div>`).join("")}</div>`,
  );
}
function findingsView() {
  let rows = filtered(state.findings);
  return (
    heading(
      "Findings",
      "Evidence review before confirmation. Public references inform comparison, never eligibility.",
      state.engagements.length
        ? '<button class="btn primary" data-action="finding">＋ Add finding</button>'
        : "",
    ) +
    `<div class="toolbar">${engagementFilter()}</div>` +
    panel(
      "Review queue",
      rows.length
        ? `<div class="table-wrap"><table><thead><tr><th>Finding</th><th>Severity</th><th>Status</th><th>Readiness</th><th></th></tr></thead><tbody>${rows.map((f) => `<tr><td><strong>${esc(f.title)}</strong><div class="sub path">${esc(f.target)} · ${esc(engagementName(f.engagement_id))}</div></td><td>${pill(f.severity)}</td><td>${pill(f.status)}</td><td>${pill(f.readiness?.disposition || "needs_evidence")}<div class="sub">${f.readiness?.completed || 0} / ${f.readiness?.total || 18} checks</div></td><td><button class="btn small" data-action="edit-finding" data-id="${f.id}">Review →</button></td></tr>`).join("")}</tbody></table></div>`
        : empty(
            "No findings recorded",
            "Scanner matches begin unverified. Add reproducible evidence before confirming impact.",
          ),
    )
  );
}
function referenceCards(rows) {
  if (!rows.length)
    return empty(
      "No matching public reports",
      "Import publicly disclosed HackerOne report URLs. Current target eligibility must be checked separately.",
    );
  return rows
    .map(
      (r) =>
        `<article class="tool-card reference-card"><div class="row spread"><h3>#${esc(r.report_id)} · ${esc(r.program)}</h3>${pill(r.outcome)}</div><h3>${esc(r.title)}</h3><p>${esc(r.weakness || "Weakness not specified")} · ${esc(r.severity)}</p><div class="reference-meta">${r.rewarded === true ? `<span class="pill ready">Reward visible: ${esc(r.bounty_amount)} ${esc(r.currency)}</span>` : `<span class="pill">${r.rewarded === false ? "No positive reward shown" : "Reward unknown"}</span>`}<span class="help">Disclosed ${esc(r.disclosed_at?.slice(0, 10))}</span></div><footer><span>Public metadata · ${when(r.fetched_at)}</span><button class="btn small" data-action="reference-detail" data-id="${esc(r.id)}">Read reference ↗</button></footer></article>`,
    )
    .join("");
}
function referencesView() {
  return (
    heading(
      "Public report library",
      "Historical outcomes and evidence patterns, with source links and disclosure dates.",
      '<button class="btn primary" data-action="import-references">＋ Import public reports</button>',
    ) +
    '<div class="note neutral">A reward in another report does not establish eligibility or severity here. Disclosures can be outdated or incomplete. Private reports and attachments are not collected.</div>' +
    `<div class="toolbar"><input id="reference-search" aria-label="Search public reports" placeholder="Search title, program, weakness or outcome…"><select id="reference-filter" aria-label="Filter public reports"><option value="all">All outcomes</option><option value="rewarded">Visible reward</option><option value="valid">Triaged / resolved</option><option value="informative">Informative / not applicable</option></select><button class="btn" data-action="discover-references">Search HackerOne API ↗</button></div><div class="tool-grid" id="reference-grid">${referenceCards(state.references || [])}</div>`
  );
}
function filterReferences() {
  const query = $("#reference-search").value.toLowerCase(),
    filter = $("#reference-filter").value;
  $("#reference-grid").innerHTML = referenceCards(
    (state.references || []).filter(
      (r) =>
        [r.title, r.program, r.weakness, r.outcome]
          .join(" ")
          .toLowerCase()
          .includes(query) &&
        (filter === "all" ||
          (filter === "rewarded" && r.rewarded === true) ||
          (filter === "valid" && ["triaged", "resolved"].includes(r.outcome)) ||
          (filter === "informative" &&
            ["informative", "not-applicable", "not_applicable"].includes(
              r.outcome,
            ))),
    ),
  );
}
function importReferenceModal() {
  modal(
    "Import public reports",
    "Paste up to five HackerOne report URLs or numeric IDs. Imports are cached locally and rate-limited.",
    `<form id="reference-import-form"><label>Public report URLs / IDs</label><textarea name="urls" rows="5" placeholder="https://hackerone.com/reports/123456"></textarea><label class="check-label"><input type="checkbox" name="refresh">Refresh previously cached metadata</label><p class="help">Anonymous fetch only. No saved engagement credentials are sent. Only explicitly public, disclosed reports are retained.</p><div class="inline-error" id="form-error"></div><div id="reference-result" role="status"></div><div class="form-actions"><button class="btn primary">Import references</button></div></form>`,
  );
}
function discoverReferenceModal() {
  modal(
    "Search public HackerOne reports",
    "Uses the documented Hacktivity API; only explicitly disclosed results are shown.",
    `<form id="reference-discover-form"><label>Lucene query (optional)</label><input name="query" placeholder="team:gitlab AND total_awarded_amount:>0"><label>Page (10 results)</label><input name="page" type="number" min="1" max="100" value="1"><div class="note neutral">${state.reference_search_enabled ? "HackerOne API credentials are configured in the server environment." : "Set KIROSHI_H1_API_USERNAME and KIROSHI_H1_API_TOKEN in your WSL environment, then restart the dashboard. Public URL imports work without API credentials."}</div><div class="inline-error" id="form-error"></div><div class="form-actions"><button class="btn primary" ${state.reference_search_enabled ? "" : "disabled"}>Search disclosed reports</button></div></form><div id="discovery-results"></div>`,
  );
}
function referenceDetail(id) {
  const r = state.references.find((r) => r.id === id);
  modal(
    `Public report #${esc(r.report_id)}`,
    "Untrusted reference content. Historical outcome does not establish eligibility for your finding.",
    `<div class="stack"><h3>${esc(r.title)}</h3><div class="row">${pill(r.outcome)}<span class="pill">${esc(r.program)}</span><span class="pill">${r.rewarded === true ? "Visible reward" : "Reward not established"}</span></div><p>${esc(r.eligibility)}</p><label>Short public excerpt</label><pre class="terminal">${esc(r.excerpt || "No description was visible in the public response.")}</pre><div><a href="${esc(r.source_url)}" target="_blank" rel="noopener noreferrer">Open original disclosure ↗</a></div><p class="help">Disclosed: ${esc(r.disclosed_at)} · Retrieved: ${esc(r.fetched_at)} · Source fingerprint: ${esc(r.source_hash.slice(0, 16))}</p></div>`,
  );
}
function readinessSummary(readiness) {
  if (!readiness)
    return '<div class="note neutral">Complete the evidence review, then check readiness. Drafts can be saved with gaps.</div>';
  return `<div class="review-result"><div class="row spread">${pill(readiness.disposition)}<span>${readiness.completed} / ${readiness.total} complete</span></div><ul class="review-checks">${readiness.checks.map((c) => `<li class="${c.passed ? "check-pass" : "check-gap"}"><span>${c.passed ? "✓" : "○"}</span><div>${esc(c.label)}<small>${esc(c.reason)}</small></div></li>`).join("")}</ul><p class="help">${esc(readiness.notice)}</p></div>`;
}
function toolsView() {
  return (
    heading(
      "Your WSL toolchain",
      `${state.tools.length} catalog entries. ${state.tools.filter(toolReady).length} installed tools have runnable adapters.`,
      '<button class="btn" data-action="check-tools">Check binaries ↻</button>',
    ) +
    `<div class="note neutral"><strong>HTTP User-Agent</strong><br><code class="path">${esc(state.http_user_agent || "Restart the dashboard to load HTTP identity")}</code><p class="help">Used by the HTTP adapters and reference collector. Subfinder manages its own browser identity; DNS/TLS have no User-Agent.</p></div><div class="note neutral">Ready adapters can be launched from an engagement. Inventory-only entries are detected but require an adapter before this dashboard can run them. No tools are installed automatically.</div><div class="toolbar"><input id="tool-search" placeholder="Search tools or categories…" aria-label="Search toolchain"><select id="tool-filter" aria-label="Tool availability"><option value="all">All tools</option><option value="ready">Ready to run</option><option value="installed">Installed</option><option value="missing">Missing</option></select></div><div class="tool-grid" id="tool-grid">${toolCards(state.tools)}</div>`
  );
}
function toolCards(rows) {
  return rows
    .map(
      (t) =>
        `<article class="tool-card"><div class="row spread"><h3>${esc(t.name)}</h3>${pill(t.installed ? (t.compatibility === "incompatible" ? "incompatible" : t.adapter ? "ready" : "installed") : "missing")}</div><p>${esc(t.description)}</p><code title="${esc(t.path || "Not found on WSL PATH")}">${esc(t.path || "Not found on WSL PATH")}</code><p class="help">${esc(t.source || "autodetected")} · ${esc(t.compatibility || "not_checked")}</p>${t.override_warning ? `<p class="help">${esc(t.override_warning)}</p>` : ""}<footer><span>${esc(t.category)} · ${t.adapter ? "Runnable adapter" : "Inventory only"}</span><button class="btn small" data-action="tool-path" data-id="${esc(t.name)}">Path</button></footer></article>`,
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
            "Agent workspaces are generated from the scaffold script.",
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
    references: "Public reports",
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
    references: referencesView,
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
function scopeTarget(e) {
  const rule = e.scope.find((r) => !r.includes("*.")) || "";
  return rule.includes("://") ? rule : "https://" + rule;
}
function engagementModal(id) {
  const e = state.engagements.find((x) => x.id === id) || {};
  modal(
    id ? "Edit engagement" : "New engagement",
    "Define the authorized boundary before running tools.",
    `<form id="engagement-form"><input type="hidden" name="id" value="${e.id || ""}"><div class="form-grid">${field("Engagement name", "name", e.name || "")}${field("Program / policy URL", "policy", e.policy || "")}<div><label>In-scope hosts or URLs (one per line)</label><textarea name="scope" required placeholder="example.com&#10;*.example.com">${esc((e.scope || []).join("\n"))}</textarea><div class="help">Paste hostnames, IPs, wildcards or HTTP(S) URLs. Root URLs become host rules. URL paths stay restricted; current scan adapters require whole-host scope. A wildcard does not include the apex.</div></div><div><label>Excluded hosts or URLs</label><textarea name="excluded" placeholder="payments.example.com">${esc((e.excluded || []).join("\n"))}</textarea></div>${field("Rate ceiling / second", "rate", e.rate || 5, "number")}${field("Maximum job duration / seconds", "duration", e.duration || 300, "number")}<div><label>Preferred agent client</label><select name="provider"><option value="claude" ${e.provider === "claude" ? "selected" : ""}>Claude Code (your configured provider)</option><option value="codex" ${e.provider === "codex" ? "selected" : ""}>Codex</option></select></div><div><label>Program notes / constraints</label><textarea name="notes">${esc(e.notes || "")}</textarea></div><label class="check-label full"><input name="authorized" type="checkbox" required ${e.authorized ? "checked" : ""}>I have authorization for these assets and have reviewed the program’s testing rules.</label></div>${trafficEditor(e)}<div class="inline-error" id="form-error"></div><div class="form-actions"><button type="button" class="btn" data-action="close">Cancel</button><button class="btn primary">Save engagement</button></div></form>`,
  );
}
function trafficEditor(e) {
  const t = e.traffic || {};
  const statuses = t.block_statuses || [429, 503];
  return `<details class="review-section"><summary>Traffic & block-response controls</summary><div class="form-grid">${field("Worker concurrency (1–10)", "traffic_concurrency", t.concurrency || 1, "number")}${field("Request timeout (3–60 seconds)", "traffic_timeout", t.timeout || 10, "number")}${field("Consecutive block signals before stopping", "traffic_block_threshold", t.block_threshold || 1, "number")}${field("Minimum cooldown (seconds)", "traffic_cooldown", t.cooldown || 30, "number")}<div class="full"><label>Statuses to monitor</label><div class="row">${[429, 503, 403].map((code) => `<label class="check-label"><input name="block_${code}" type="checkbox" ${statuses.includes(code) ? "checked" : ""}>HTTP ${code}</label>`).join("")}</div><p class="help">403 is optional: access-denied responses often reflect expected permissions rather than a WAF.</p></div><label class="check-label full"><input name="traffic_stop_on_block" type="checkbox" ${t.stop_on_block !== false ? "checked" : ""}>Stop on observed block signals and cool down queued runs to this origin</label></div><p class="help">Feedback is limited to responses emitted by each scanner. This is not transparent WAF detection, challenge solving or a network firewall.</p></details>`;
}
function sessionModal(engagementId, sessionId) {
  const s = state.sessions.find((s) => s.id === sessionId) || {};
  const e = state.engagements.find((e) => e.id === engagementId);
  modal(
    sessionId ? "Replace session" : "Add session",
    "Stored locally with restricted file permissions. Values are never returned by the API.",
    `<form id="session-form"><input type="hidden" name="engagement_id" value="${e.id}"><input type="hidden" name="id" value="${s.id || ""}"><div class="form-grid">${field("Identity / session label", "label", s.label || "Account A")}${field("Exact origin (scheme, host, port)", "origin", s.origin || new URL(scopeTarget(e)).origin)}<div class="full"><label>Cookie header value</label><input type="password" name="cookie" autocomplete="off" placeholder="session=…; csrf=…"></div><div class="full"><label>Additional headers (one Name: Value per line)</label><textarea name="headers" autocomplete="off" spellcheck="false" placeholder="Authorization: Bearer …&#10;X-CSRF-Token: …"></textarea><div class="help">Exact-origin binding. Redirects stay disabled. Replacing a session affects future runs only.</div></div></div><div class="inline-error" id="form-error"></div><div class="form-actions"><button type="button" class="btn" data-action="close">Cancel</button><button class="btn primary">Save session</button></div></form>`,
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
  const ready = state.tools.filter(toolReady);
  modal(
    "New tool run",
    "Preview a bounded command. Existing recon stays cached.",
    `<form id="run-form"><div class="form-grid"><div><label>Engagement</label><select name="engagement_id" id="run-engagement">${state.engagements.map((x) => `<option value="${x.id}" ${x.id === e.id ? "selected" : ""}>${esc(x.name)}</option>`).join("")}</select></div><div><label>Tool / profile</label><select name="tool" id="run-tool">${ready.map((t) => `<option value="${t.name}" ${t.name === "httpx" ? "selected" : ""}>${esc(t.name)} — ${esc(t.description)}</option>`).join("")}</select></div><div class="full"><label>Target host or URL</label><input name="target" required value="${esc(target || scopeTarget(e))}" placeholder="https://app.example.com"></div><div class="full"><label>Identity / session</label><select name="auth_id" id="run-session"></select><div class="help">HTTP sessions are sent only to their exact origin. DNS/recon/TLS profiles use Anonymous.</div></div></div>${runTrafficFields(e)}<label class="check-label"><input type="checkbox" name="allow_repeat">Repeat completed run (explicitly rerun this tool, target and session)</label><div class="note neutral">Nuclei runs the bundled server-header inventory template. Content discovery uses a small bundled wordlist. Broader templates and wordlists need an adapter extension.</div><div class="preview-box" id="command-preview"></div><div class="inline-error" id="form-error"></div><div class="form-actions"><button type="button" class="btn" data-action="preview">Preview command</button><button class="btn primary" ${ready.length ? "" : "disabled"}>Queue run →</button></div></form>`,
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
  updateRunTraffic();
}
function runTrafficFields(e) {
  return `<details class="review-section"><summary>Run pacing</summary><div class="form-grid"><div><label>Traffic profile</label><select name="traffic_profile" id="run-traffic-profile"><option value="inherit">Engagement settings</option><option value="gentle">Gentle · 1 request/sec, 1 worker</option></select></div>${field("Run rate (cannot exceed engagement ceiling)", "rate", e.rate, "number")}<div><label>Extra delay (milliseconds)</label><input name="delay_ms" type="number" min="0" max="60000" value="0"><p class="help">Supported by httpx, Katana, ffuf and tlsx.</p></div><div><label>Delay jitter (milliseconds)</label><input name="jitter_ms" type="number" min="0" max="5000" value="0"><p class="help">ffuf only. Controls are disabled for unsupported adapters.</p></div></div><p class="help" id="run-traffic-note"></p></details>`;
}
function updateRunTraffic() {
  const form = $("#run-form");
  if (!form) return;
  const tool = form.elements.tool.value,
    gentle = form.elements.traffic_profile.value === "gentle";
  const e = state.engagements.find(
    (e) => e.id === form.elements.engagement_id.value,
  );
  form.elements.rate.max = e.rate;
  form.elements.rate.value = Math.min(
    Number(form.elements.rate.value) || e.rate,
    e.rate,
  );
  form.elements.rate.disabled = gentle;
  form.elements.delay_ms.disabled =
    gentle || !["httpx", "katana", "ffuf", "tlsx"].includes(tool);
  form.elements.jitter_ms.disabled = gentle || tool !== "ffuf";
  if (form.elements.delay_ms.disabled) form.elements.delay_ms.value = 0;
  if (form.elements.jitter_ms.disabled) form.elements.jitter_ms.value = 0;
  $("#run-traffic-note").textContent =
    `Engagement ceiling: ${e.rate}/s. Retries are disabled where supported. Block feedback depends on scanner output; a 403 alone does not identify a WAF.`;
}
function findingModal(id) {
  const f = state.findings.find((f) => f.id === id) || {};
  modal(
    id ? "Review finding" : "Record finding",
    "Save a draft at any stage. Confirmed/reported requires a complete, attested evidence review.",
    `<form id="finding-form"><input type="hidden" name="id" value="${f.id || ""}"><div class="form-grid"><div class="full"><label>Engagement</label><select name="engagement_id">${state.engagements
      .filter((e) => !f.id || e.id === f.engagement_id)
      .map(
        (e) =>
          `<option value="${e.id}" ${e.id === (f.engagement_id || selected) ? "selected" : ""}>${esc(e.name)}</option>`,
      )
      .join(
        "",
      )}</select></div>${field("Title", "title", f.title || "")}${field("Affected target", "target", f.target || "")}<div><label>Severity</label><select name="severity">${["info", "low", "medium", "high", "critical"].map((v) => `<option ${v === (f.severity || "info") ? "selected" : ""}>${v}</option>`).join("")}</select></div><div><label>Status</label><select name="status">${["unverified", "confirmed", "dismissed", "reported"].map((v) => `<option ${v === (f.status || "unverified") ? "selected" : ""}>${v}</option>`).join("")}</select></div><div class="full"><label>Evidence and notes (Markdown)</label><textarea name="notes" rows="6">${esc(f.notes || "## Impact\n\n## Reproduction steps\n\n## Evidence\n")}</textarea></div></div>${reviewForm(f)}<div class="inline-error" id="form-error"></div><div class="form-actions"><button type="button" class="btn" data-action="check-readiness">Check readiness</button><button class="btn primary">Save finding</button></div></form>`,
  );
}
function reviewForm(f) {
  const r = f.review || {};
  const choice = (label, name, values) =>
    `<div><label>${label}</label><select name="review_${name}">${values.map(([value, text]) => `<option value="${value}" ${value === (r[name] || "unknown") ? "selected" : ""}>${text}</option>`).join("")}</select></div>`;
  return `<details class="review-section" open><summary>Evidence & eligibility review</summary><div class="note neutral">These checks assess completeness and your attestations. They do not independently verify exploitation. References never override policy or replace your own evidence.</div><div class="form-grid">${choice(
    "Current policy eligibility",
    "eligibility",
    [
      ["unknown", "Not reviewed"],
      ["eligible", "Accepted asset and class"],
      ["excluded", "Excluded by policy"],
    ],
  )}${choice("Impact assessment", "impact_assessment", [
    ["unknown", "Not established"],
    ["demonstrated", "Demonstrated security impact"],
    ["informational", "Informational only"],
    ["expected_behavior", "Expected behavior"],
  ])}${choice("False-positive alternatives", "false_positive_assessment", [
    ["unknown", "Not investigated"],
    ["ruled_out", "Addressed using controls"],
    ["identified", "Alternative explanation identified"],
  ])}${field("Independent reproductions", "review_reproduction_attempts", r.reproduction_attempts || 0, "number")}${field("Policy review date", "review_policy_checked_at", r.policy_checked_at || "", "date")}${field("Reviewer name / handle", "review_reviewer", r.reviewer || "")}${Object.entries(
    state.review_fields || {},
  )
    .map(
      ([key, label]) =>
        `<div class="full"><label for="review-${key}">${esc(label)}</label><textarea id="review-${key}" name="review_${key}" rows="2" placeholder="Specific evidence, observations or local evidence references…">${esc(r[key] || "")}</textarea></div>`,
    )
    .join(
      "",
    )}<div class="full"><label>Linked public reference reports (optional; Ctrl/Cmd to select several)</label><select name="reference_ids" multiple size="4">${(state.references || []).map((ref) => `<option value="${esc(ref.id)}" ${(r.reference_ids || []).includes(ref.id) ? "selected" : ""}>#${esc(ref.report_id)} · ${esc(ref.program)} · ${esc(ref.outcome)} · ${esc(ref.title)}</option>`).join("")}</select><p class="help">Public similarities cannot rule out an undisclosed duplicate or establish present eligibility.</p></div><label class="check-label full"><input type="checkbox" name="review_attested">I reviewed this finding’s evidence and current program policy. These are my observations; assumptions and limitations are stated.</label></div></details><div id="readiness-result">${readinessSummary(f.readiness)}</div>${(f.related_references || []).length ? `<details class="review-section"><summary>Related public reports · lexical matches</summary>${f.related_references.map((r) => `<p><a href="${esc(r.source_url)}" target="_blank" rel="noopener noreferrer">#${esc(r.report_id)} ${esc(r.title)}</a> · ${esc(r.outcome)}<span class="help">Matched terms: ${r.match_terms.map(esc).join(", ") || "Manually linked"}</span></p>`).join("")}</details>` : ""}`;
}
function findingPayload(form) {
  const data = Object.fromEntries(new FormData(form));
  const review = {};
  for (const [key, value] of Object.entries(data))
    if (key.startsWith("review_")) {
      review[key.slice(7)] = value;
      delete data[key];
    }
  review.reproduction_attempts = Number(review.reproduction_attempts || 0);
  review.attested = form.elements.review_attested.checked;
  review.reference_ids = [...form.elements.reference_ids.selectedOptions].map(
    (o) => o.value,
  );
  delete data.reference_ids;
  if (!data.id) delete data.id;
  return { ...data, review };
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
    `<div class="log-toolbar"><div class="row"><strong class="mono">${esc(job.tool)}</strong>${pill(job.status)}<span class="text-muted">${esc(job.identity || "Anonymous")}</span></div><div class="row"><a class="btn small" href="/api/jobs/${job.id}/download" download>Download</a><button class="btn small" data-action="rerun" data-id="${job.id}">Run again</button>${pending(job) ? `<button class="btn small danger" data-action="cancel-job" data-id="${job.id}">Cancel job</button>` : ""}</div></div><p class="help path">${esc(job.display)}</p><p class="help">${job.error ? esc(job.error) : "Exit code: " + (job.returncode ?? "pending")}</p><p class="help">${esc(job.result_summary || "")}</p>${job.processing_error ? `<div class="note neutral">${esc(job.processing_error)}</div>` : ""}<p class="help">Finished means the process exited successfully; observations still need review. A redirect is not a vulnerability.</p>${
      (job.traffic_events || []).length
        ? `<div class="note neutral">${job.traffic_events
            .map(
              (e) =>
                `Observed HTTP ${e.status_code}; minimum cooldown ${e.delay}s${e.manual_hold ? " · manual hold" : ""}`,
            )
            .map(esc)
            .join("<br>")}</div>`
        : ""
    }`;
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
          `<label>COMMAND PREVIEW · ${esc(p.identity)} · ${p.duration}s limit</label><pre class="terminal">${esc(p.display)}</pre><p class="help">${esc(p.auth_notice)}</p><p class="help">${p.traffic.rate}/s · ${p.traffic.concurrency} worker(s) · ${p.traffic.timeout}s timeout · ${p.traffic.delay_ms}ms delay · ${p.traffic.jitter_ms}ms jitter</p>`;
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
      case "check-readiness": {
        const checked = await api(
          "findings/check",
          findingPayload($("#finding-form")),
        );
        $("#readiness-result").innerHTML = readinessSummary(checked.readiness);
        $("#readiness-result").scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
        break;
      }
      case "import-references":
        importReferenceModal();
        break;
      case "discover-references":
        discoverReferenceModal();
        break;
      case "reference-detail":
        referenceDetail(id);
        break;
      case "import-discovered": {
        el.disabled = true;
        try {
          const result = await api("references/import", { urls: [id] });
          await refresh(false);
          toast(
            result.errors.length
              ? result.errors[0].error
              : "Public report cached",
            !!result.errors.length,
          );
        } finally {
          el.disabled = false;
        }
        break;
      }
      case "edit-finding":
        findingModal(id);
        break;
      case "tool-path": {
        const tool = state.tools.find((t) => t.name === id);
        modal(
          "Configure " + esc(id),
          "Paths belong to this installation only. Leave the override empty to use autodetection.",
          `<form id="path-form"><input type="hidden" name="tool" value="${esc(id)}">${field("Executable path override", "path", tool.configured_path || "")}<p class="help path">Autodetected: ${esc(tool.detected_path || "Not found")} · ${esc(tool.diagnostic || "")}</p><div class="inline-error" id="form-error"></div><div class="form-actions"><button class="btn primary">Save executable path</button></div></form>`,
        );
        break;
      }
      case "check-tools": {
        el.disabled = true;
        el.textContent = "Checking…";
        try {
          await api("tools/check", {});
          await refresh();
          toast("Local adapter compatibility checked");
        } finally {
          el.disabled = false;
        }
        break;
      }
      case "clear-traffic": {
        const gate = (state.traffic_gates || []).find((g) => g.id === id);
        modal(
          "Review traffic hold",
          "Clearing this hold allows queued runs to resume. Confirm the program permits your next test.",
          `<form id="traffic-clear-form"><input name="id" type="hidden" value="${id}"><p class="mono path">${esc(gate.origin)} · HTTP ${gate.status_code}</p><label>Reason for clearing the hold</label><textarea name="reason" required minlength="10" placeholder="Program-approved retest after adjusting the request rate…"></textarea><div class="inline-error" id="form-error"></div><div class="form-actions"><button class="btn primary">Clear traffic hold</button></div></form>`,
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
  if (form.dataset.submitting) return;
  form.dataset.submitting = "true";
  const data = Object.fromEntries(new FormData(form));
  try {
    if (form.getAttribute("id") === "engagement-form") {
      data.authorized = form.elements.authorized.checked;
      data.traffic = {
        concurrency: data.traffic_concurrency,
        timeout: data.traffic_timeout,
        block_threshold: data.traffic_block_threshold,
        cooldown: data.traffic_cooldown,
        stop_on_block: form.elements.traffic_stop_on_block.checked,
        block_statuses: [429, 503, 403].filter(
          (code) => form.elements["block_" + code].checked,
        ),
      };
      for (const key of Object.keys(data))
        if (key.startsWith("traffic_") || key.startsWith("block_"))
          delete data[key];
      if (!data.id) delete data.id;
      const e = await api("engagements", data);
      selected = e.id;
      view = "engagements";
    } else if (form.getAttribute("id") === "session-form") {
      if (!data.id) delete data.id;
      await api("sessions", data);
      form.reset();
    } else if (form.getAttribute("id") === "run-form") {
      data.allow_repeat = form.elements.allow_repeat.checked;
      await api("jobs", data);
      view = "jobs";
      selected = data.engagement_id;
    } else if (form.getAttribute("id") === "finding-form") {
      await api("findings", findingPayload(form));
    } else if (form.getAttribute("id") === "reference-import-form") {
      const button = form.querySelector(
        "button[type=submit],button.btn.primary",
      );
      button.disabled = true;
      button.textContent = "Importing…";
      try {
        const result = await api("references/import", {
          urls: data.urls,
          refresh: form.elements.refresh.checked,
        });
        await refresh(false);
        $("#reference-result").textContent =
          `${result.imported.length} imported · ${result.cached.length} cached`;
        $("#form-error").textContent = result.errors
          .map((e) => `#${e.report_id}: ${e.error}`)
          .join("\n");
        if (!result.errors.length) {
          closeModal();
          view = "references";
          render();
          toast("Public reports cached");
        }
      } finally {
        button.disabled = false;
        button.textContent = "Import references";
      }
      return;
    } else if (form.getAttribute("id") === "reference-discover-form") {
      const results = await api("references/discover", data);
      $("#discovery-results").innerHTML = results.results.length
        ? `<div class="stack">${results.results.map((r) => `<article class="session-card"><h3>#${esc(r.report_id)} ${esc(r.title)}</h3><p>${esc(r.outcome)} · Disclosed ${esc(r.disclosed_at.slice(0, 10))}</p><button type="button" class="btn small" data-action="import-discovered" data-id="${esc(r.report_id)}">Import public reference</button></article>`).join("")}</div>`
        : "<p>No explicitly disclosed reports matched this page.</p>";
      return;
    } else if (form.getAttribute("id") === "path-form") {
      const paths = Object.fromEntries(
        state.tools
          .filter((t) => t.configured_path)
          .map((t) => [t.name, t.configured_path]),
      );
      if (data.path.trim()) paths[data.tool] = data.path.trim();
      else delete paths[data.tool];
      await api("settings", { paths });
    } else if (form.getAttribute("id") === "traffic-clear-form") {
      await api("traffic/clear", data);
    } else return;
    closeModal();
    await refresh();
    toast("Saved locally");
  } catch (error) {
    $("#form-error").textContent = error.message;
  } finally {
    delete form.dataset.submitting;
  }
});
document.addEventListener("change", (event) => {
  if (event.target.id === "run-traffic-profile") updateRunTraffic();
  if (event.target.id === "reference-filter") filterReferences();
  if (event.target.id === "engagement-filter") {
    selected = event.target.value;
    render();
  }
  if (["run-engagement", "run-tool"].includes(event.target.id))
    updateRunSessions();
  if (event.target.id === "tool-filter") filterTools();
});
document.addEventListener("input", (event) => {
  if (event.target.id === "reference-search") filterReferences();
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
