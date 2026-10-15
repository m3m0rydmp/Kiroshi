// Optional Chrome smoke test using its native DevTools pipe; no npm dependencies.
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { mkdtemp, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import assert from "node:assert/strict";

const directory = await mkdtemp(join(tmpdir(), "kiroshi-browser-"));
const server = spawn(
  "python3",
  [
    "-m",
    "dashboard.server",
    "--port",
    "0",
    "--data-dir",
    join(directory, "data"),
  ],
  { stdio: ["ignore", "pipe", "pipe"] },
);
let chrome, webhookReceiver;
try {
  const base = await new Promise((resolve, reject) => {
    const timeout = setTimeout(
      () => reject(new Error("Server startup timeout")),
      10000,
    );
    server.stdout.on("data", (chunk) => {
      const match = String(chunk).match(/http:\/\/127\.0\.0\.1:\d+/);
      if (match) {
        clearTimeout(timeout);
        resolve(match[0]);
      }
    });
    server.on("error", reject);
  });
  chrome = spawn(
    process.env.KIROSHI_CHROME || "/usr/bin/google-chrome",
    [
      "--headless=new",
      "--no-sandbox",
      "--disable-gpu",
      "--disable-background-networking",
      "--no-first-run",
      "--no-default-browser-check",
      "--remote-debugging-pipe",
      `--user-data-dir=${join(directory, "chrome")}`,
    ],
    { stdio: ["ignore", "ignore", "pipe", "pipe", "pipe"] },
  );
  let sequence = 0,
    buffer = "";
  const pending = new Map();
  chrome.stdio[4].on("data", (chunk) => {
    buffer += chunk.toString();
    let split;
    while ((split = buffer.indexOf("\0")) >= 0) {
      const raw = buffer.slice(0, split);
      buffer = buffer.slice(split + 1);
      if (!raw) continue;
      const msg = JSON.parse(raw);
      if (pending.has(msg.id)) {
        const { resolve, reject, timer } = pending.get(msg.id);
        clearTimeout(timer);
        pending.delete(msg.id);
        msg.error
          ? reject(new Error(JSON.stringify(msg.error)))
          : resolve(msg.result);
      }
    }
  });
  const cdp = (method, params = {}, sessionId) =>
    new Promise((resolve, reject) => {
      const id = ++sequence;
      const timer = setTimeout(() => {
        pending.delete(id);
        reject(new Error("CDP timeout: " + method));
      }, 15000);
      pending.set(id, { resolve, reject, timer });
      chrome.stdio[3].write(
        JSON.stringify({
          id,
          method,
          params,
          ...(sessionId ? { sessionId } : {}),
        }) + "\0",
      );
    });
  const { targetId } = await cdp("Target.createTarget", { url: "about:blank" });
  const { sessionId } = await cdp("Target.attachToTarget", {
    targetId,
    flatten: true,
  });
  const page = (method, params) => cdp(method, params, sessionId);
  await page("Page.enable");
  await page("Runtime.enable");
  await page("Emulation.setDeviceMetricsOverride", {
    width: 1440,
    height: 1000,
    deviceScaleFactor: 1,
    mobile: false,
  });
  await page("Page.navigate", { url: base });
  const evaluate = async (expression) => {
    const result = await page("Runtime.evaluate", {
      expression,
      awaitPromise: true,
      returnByValue: true,
    });
    if (result.exceptionDetails)
      throw new Error(JSON.stringify(result.exceptionDetails));
    return result.result.value;
  };
  const wait = async (expression) => {
    for (let i = 0; i < 80; i++) {
      if (await evaluate(expression)) return;
      await new Promise((r) => setTimeout(r, 100));
    }
    throw new Error(
      "UI wait failed: " +
        expression +
        " / " +
        (await evaluate(
          "JSON.stringify({error:document.querySelector('#form-error')?.textContent,title:document.querySelector('h1')?.textContent,invalid:[...document.querySelectorAll('input,textarea')].filter(x=>!x.checkValidity()).map(x=>({name:x.name,value:x.value,validation:x.validationMessage}))})",
        )),
    );
  };
  await wait(
    "document.querySelector('h1')?.textContent.includes('next finding starts')",
  );
  assert.equal(await evaluate("document.querySelectorAll('.stat').length"), 4);
  const screenshot = await page("Page.captureScreenshot", {
    format: "png",
    captureBeyondViewport: true,
  });
  await writeFile(
    "/tmp/kiroshi-overview.png",
    Buffer.from(screenshot.data, "base64"),
  );
  await evaluate(
    "document.querySelector('[data-action=\"new-engagement\"]').click()",
  );
  await wait("document.querySelector('#engagement-form') !== null");
  assert.equal(
    await evaluate(
      "getComputedStyle(document.querySelector('#modal'), '::backdrop').backdropFilter",
    ),
    "none",
  );
  await evaluate(
    `(()=>{const f=document.querySelector('#engagement-form');f.elements.name.value='Local lab / UI check';f.elements.scope.value='http://127.0.0.1/\\nhttps://hackerone.com/mcp\\nhttps://*.hackerone-user-content.com/';f.elements.policy.value='Loopback fixture only';f.elements.authorized.checked=true;f.requestSubmit();})()`,
  );
  await wait(
    "!document.querySelector('dialog').open && document.querySelector('h1')?.textContent.includes('Local lab')",
  );
  await evaluate("document.querySelector('[data-action=\"session\"]').click()");
  await evaluate(
    `(()=>{const f=document.querySelector('#session-form');f.elements.origin.value='http://127.0.0.1:9999';f.elements.label.value='Account A';f.elements.cookie.value='session=ui-local-secret';f.elements.headers.value='Authorization: Bearer ui-local-token';f.requestSubmit();})()`,
  );
  await wait(
    "!document.querySelector('dialog').open && document.body.textContent.includes('Account A')",
  );
  assert.equal(
    await evaluate("document.body.textContent.includes('ui-local-secret')"),
    false,
  );
  await evaluate("document.querySelector('[data-action=\"run\"]').click()");
  await evaluate(
    "document.querySelector('#run-form').elements.target.value='http://127.0.0.1:9999';document.querySelector('#run-session').selectedIndex=1;document.querySelector('[data-action=\"preview\"]').click()",
  );
  await wait(
    "document.querySelector('#command-preview').textContent.includes('Account A')",
  );
  assert.equal(
    await evaluate(
      "document.querySelector('#command-preview').textContent.includes('ui-local-secret')",
    ),
    false,
  );
  await evaluate("document.querySelector('[data-action=\"close\"]').click()");
  await evaluate("document.querySelector('[data-view=\"agent\"]').click()");
  await wait(
    "document.querySelector('#agent-command')?.textContent.includes('claude')",
  );
  await evaluate(
    "document.querySelector('#handoff-text').value='Continue local fixture checks.';document.querySelector('[data-action=\"save-handoff\"]').click()",
  );
  await wait(
    "document.querySelector('#toast')?.textContent === 'Handoff saved'",
  );
  await evaluate("document.querySelector('[data-view=\"tools\"]').click()");
  assert.equal(
    await evaluate("document.querySelectorAll('.tool-card').length"),
    36,
  );
  await evaluate(
    "document.querySelector('#tool-search').value='katana';document.querySelector('#tool-search').dispatchEvent(new Event('input',{bubbles:true}))",
  );
  assert.equal(
    await evaluate("document.querySelectorAll('.tool-card').length"),
    1,
  );
  await evaluate(
    "document.querySelector('[data-action=\"tool-path\"]').click()",
  );
  await evaluate(
    "(async()=>{const s=await (await fetch('/api/state')).json();document.querySelector('#path-form').elements.path.value=s.tools.find(t=>t.name==='katana').path;document.querySelector('#path-form').requestSubmit();})()",
  );
  await wait("!document.querySelector('dialog').open");
  assert.equal(
    await evaluate(
      "(async()=>{const s=await (await fetch('/api/state')).json();return s.tools.filter(t=>t.configured_path).length;})()",
    ),
    1,
  );
  await evaluate(
    "document.querySelector('[data-action=\"tool-path\"][data-id=\"katana\"]').click();document.querySelector('#path-form').elements.path.value='';document.querySelector('#path-form').requestSubmit()",
  );
  await wait("!document.querySelector('dialog').open");
  assert.equal(
    await evaluate(
      "(async()=>{const s=await (await fetch('/api/state')).json();return s.tools.filter(t=>t.configured_path).length;})()",
    ),
    0,
  );
  await evaluate(
    "document.querySelector('[data-view=\"jobs\"]').click();document.querySelector('[data-action=\"run\"]').click()",
  );
  await evaluate(
    "document.querySelector('#run-form').elements.target.value='http://127.0.0.1:9999';document.querySelector('#run-traffic-profile').value='gentle';document.querySelector('#run-traffic-profile').dispatchEvent(new Event('change',{bubbles:true}));document.querySelector('[data-action=\"preview\"]').click()",
  );
  await wait(
    "document.querySelector('#command-preview')?.textContent.includes('1/s')",
  );
  await evaluate("document.querySelector('[data-action=\"close\"]').click()");
  await evaluate(
    "document.querySelector('[data-view=\"findings\"]').click();document.querySelector('[data-action=\"finding\"]').click()",
  );
  await evaluate(
    `(()=>{const f=document.querySelector('#finding-form');f.elements.title.value='Local fixture access-control observation';f.elements.target.value='http://127.0.0.1:9999/owned';f.elements.status.value='confirmed';f.requestSubmit();})()`,
  );
  await wait(
    "document.querySelector('#form-error')?.textContent.includes('Evidence review required')",
  );
  await evaluate(
    "document.querySelector('#finding-form').elements.status.value='unverified';document.querySelector('#finding-form').requestSubmit()",
  );
  await wait(
    "!document.querySelector('dialog').open && document.body.textContent.includes('needs evidence')",
  );
  await evaluate(
    "document.querySelector('[data-action=\"edit-finding\"]').click()",
  );
  await evaluate(
    `(()=>{const f=document.querySelector('#finding-form');for(const input of f.querySelectorAll('textarea[name^=review_]'))input.value='Local fixture evidence with control comparisons and reproducible request references.';f.elements.review_eligibility.value='eligible';f.elements.review_impact_assessment.value='demonstrated';f.elements.review_false_positive_assessment.value='ruled_out';f.elements.review_reproduction_attempts.value=2;f.elements.review_policy_checked_at.value=new Date().toISOString().slice(0,10);f.elements.review_reviewer.value='Local fixture reviewer';f.elements.review_attested.checked=true;document.querySelector('[data-action=\"check-readiness\"]').click();})()`,
  );
  await wait(
    "document.querySelector('#readiness-result')?.textContent.includes('ready for human review')",
  );
  const reviewShot = await page("Page.captureScreenshot", {
    format: "png",
    captureBeyondViewport: true,
  });
  await writeFile(
    "/tmp/kiroshi-review.png",
    Buffer.from(reviewShot.data, "base64"),
  );
  await evaluate(
    "document.querySelector('#finding-form').elements.status.value='confirmed';document.querySelector('#finding-form').requestSubmit()",
  );
  await wait(
    "!document.querySelector('dialog').open && document.body.textContent.includes('confirmed')",
  );
  await evaluate(
    "document.querySelector('[data-view=\"references\"]').click();document.querySelector('[data-action=\"import-references\"]').click()",
  );
  assert.equal(
    await evaluate("document.querySelector('#reference-import-form')!==null"),
    true,
  );
  await evaluate(
    "document.querySelector('[data-action=\"close\"]').click();document.querySelector('[data-action=\"discover-references\"]').click()",
  );
  assert.equal(
    await evaluate("document.querySelector('#reference-discover-form')!==null"),
    true,
  );
  await evaluate("document.querySelector('[data-action=\"close\"]').click()");
  // Execution visibility uses fake binaries only; no engagement traffic is sent.
  const fakePath = join(directory, "fake-tools");
  await writeFile(
    fakePath,
    `#!/usr/bin/env python3
import json,sys,time
if '-h' in sys.argv or '--help' in sys.argv:
 print('-max-time -rate-limit -url-scope -rcode -resp-only -status-code -no-fallback-scheme -tls-version -scan-mode -crawl-scope -disable-redirects --no-recursion --rate-limit -maxtime -noninteractive -no-interactsh')
 sys.exit(0)
print('Local execution fixture started',flush=True)
time.sleep(1.5)
print(json.dumps({'url':'http://127.0.0.1:9999/fixture','status_code':200}),flush=True)
`,
    { mode: 0o700 },
  );
  await evaluate(
    `(async()=>{await api('settings',{paths:Object.fromEntries(['subfinder','dnsx','httpx','tlsx','urlfinder','katana','feroxbuster','ffuf','nuclei'].map(name=>[name,${JSON.stringify(fakePath)}]))});await refresh();navigate('jobs');})()`,
  );
  await evaluate(
    `document.querySelector('[data-action="run"]').click();(()=>{const f=document.querySelector('#run-form');f.elements.tool.value='nuclei';f.elements.tool.dispatchEvent(new Event('change',{bubbles:true}));f.elements.target.value='http://127.0.0.1:9999';f.elements.auth_id.selectedIndex=1;f.requestSubmit();})()`,
  );
  await wait(
    "document.querySelector('#job-output')?.textContent.includes('Local execution fixture started')",
  );
  assert.equal(
    await evaluate(
      "document.querySelector('#job-meta').textContent.includes('Elapsed:')",
    ),
    true,
  );
  assert.equal(
    await evaluate(
      "document.querySelector('#job-meta').textContent.includes('nuclei')",
    ),
    true,
  );
  assert.equal(
    await evaluate(
      "document.querySelector('#job-activity').textContent.includes('Started nuclei')",
    ),
    true,
  );
  await wait("state.jobs.some(j=>j.tool==='nuclei' && j.status==='completed')");
  await evaluate("document.querySelector('[data-action=rerun]').click()");
  assert.equal(
    await evaluate("document.querySelector('#run-form').elements.tool.value"),
    "nuclei",
  );
  assert.equal(
    await evaluate(
      "document.querySelector('#run-form').elements.auth_id.selectedIndex",
    ),
    1,
  );
  await evaluate(
    "(async()=>{const j=state.jobs.find(j=>j.tool==='nuclei');await api('sessions/delete',{id:j.auth_id});await refresh(false);closeModal();runModal(j.engagement_id,j.target,j);document.querySelector('#run-form').requestSubmit();})()",
  );
  await wait(
    "document.querySelector('#form-error')?.textContent.includes('Choose an available session')",
  );
  assert.equal(
    await evaluate("state.jobs.filter(j=>j.tool==='nuclei').length"),
    1,
  );
  await evaluate(
    "closeModal();document.querySelector('[data-action=workflow]').click()",
  );
  assert.equal(
    await evaluate("document.querySelector('#workflow-start').disabled"),
    true,
  );
  await evaluate(
    `(()=>{const original=window.fetch.bind(window);window.fixtureRequests={preview:0,start:0,erase:0};window.fixtureFailPreview=true;window.fetch=async(input,init)=>{const path=String(input);const kind=path.endsWith('/api/workflows/preview')?'preview':path.endsWith('/api/workflows')?'start':path.endsWith('/api/jobs/erase')?'erase':null;if(kind){window.fixtureRequests[kind]++;await new Promise(r=>setTimeout(r,1200));if(kind==='preview'&&window.fixtureFailPreview){window.fixtureFailPreview=false;return new Response(JSON.stringify({error:'Fixture preview failure'}),{status:400});}}return original(input,init);};document.querySelector('#workflow-form').elements.max_jobs.value=2;document.querySelector('[data-action=workflow-preview]').click();})()`,
  );
  assert.equal(
    await evaluate(
      "document.querySelector('#workflow-form').getAttribute('aria-busy')",
    ),
    "true",
  );
  assert.equal(
    await evaluate(
      "document.querySelector('.request-progress').textContent.includes('Preparing workflow')",
    ),
    true,
  );
  await wait(
    "document.querySelector('#form-error')?.textContent.includes('Fixture preview failure')",
  );
  assert.equal(
    await evaluate(
      "document.querySelector('#workflow-form').hasAttribute('aria-busy')",
    ),
    false,
  );
  assert.equal(
    await evaluate("document.querySelector('#workflow-start').disabled"),
    true,
  );
  await evaluate(
    "document.querySelector('[data-action=workflow-preview]').click()",
  );
  const loadingShot = await page("Page.captureScreenshot", {
    format: "png",
    captureBeyondViewport: true,
  });
  await writeFile(
    "/tmp/kiroshi-workflow-loading.png",
    Buffer.from(loadingShot.data, "base64"),
  );
  await wait("document.querySelector('#workflow-start')?.disabled===false");
  assert.equal(
    await evaluate(
      "(document.querySelector('#workflow-preview').textContent.match(/httpx/g)||[]).length",
    ),
    4,
  );
  await evaluate(
    "document.querySelector('#workflow-form').requestSubmit();document.querySelector('#workflow-form').requestSubmit()",
  );
  assert.equal(
    await evaluate(
      "document.querySelector('#workflow-form').getAttribute('aria-busy')",
    ),
    "true",
  );
  assert.equal(
    await evaluate(
      "document.querySelector('.request-progress').textContent.includes('Starting workflow')",
    ),
    true,
  );
  assert.equal(await evaluate("window.fixtureRequests.start"), 1);
  await wait(
    "document.querySelector('#workflow-meta')?.textContent.includes('Ordered stages')",
  );
  await wait(
    "document.querySelector('#workflow-meta')?.textContent.includes('Coverage limited')",
  );
  const workflowShot = await page("Page.captureScreenshot", {
    format: "png",
    captureBeyondViewport: true,
  });
  await writeFile(
    "/tmp/kiroshi-workflow.png",
    Buffer.from(workflowShot.data, "base64"),
  );
  await evaluate(
    "closeModal();navigate('jobs');document.querySelector('[data-action=erase-history]').click()",
  );
  assert.equal(
    await evaluate("document.querySelector('#erase-history-form')!==null"),
    true,
  );
  const historyCount = await evaluate("state.jobs.length");
  await evaluate(
    "document.querySelector('#erase-history-form [data-action=close]').click()",
  );
  assert.equal(await evaluate("state.jobs.length"), historyCount);
  await evaluate(
    "document.querySelector('[data-action=erase-history]').click();document.querySelector('#erase-history-form').requestSubmit()",
  );
  assert.equal(
    await evaluate(
      "document.querySelector('#erase-history-form').getAttribute('aria-busy')",
    ),
    "true",
  );
  await wait(
    "!document.querySelector('#modal').open && state.jobs.length===0 && state.workflows.length===0",
  );
  assert.equal(await evaluate("state.engagements.length"), 1);
  assert.equal(await evaluate("state.findings.length"), 1);
  assert.equal(await evaluate("state.assets.length>0"), true);
  assert.equal(await evaluate("window.fixtureRequests.erase"), 1);
  const deliveries = [];
  webhookReceiver = createServer((request, response) => {
    let raw = "";
    request.on("data", (chunk) => (raw += chunk));
    request.on("end", () => {
      deliveries.push({ headers: request.headers, body: JSON.parse(raw) });
      response.writeHead(204);
      response.end();
    });
  });
  await new Promise((resolve) =>
    webhookReceiver.listen(0, "127.0.0.1", resolve),
  );
  const hook = `http://127.0.0.1:${webhookReceiver.address().port}/private/fixture-webhook-secret`;
  await evaluate(
    `navigate('overview');(()=>{const f=document.querySelector('#notification-form');f.elements.url.value=${JSON.stringify(hook)};f.requestSubmit();})()`,
  );
  await wait(
    "document.querySelector('#notification-status')?.textContent.includes('Webhook settings saved')",
  );
  assert.equal(
    await evaluate("document.querySelector('#webhook-url').value"),
    "",
  );
  assert.equal(
    await evaluate(
      "JSON.stringify(state.notifications).includes('fixture-webhook-secret')",
    ),
    false,
  );
  await evaluate(
    "document.querySelector('[data-action=test-notification]').click()",
  );
  await wait(
    "document.querySelector('#notification-status')?.textContent.includes('Test notification sent')",
  );
  assert.equal(deliveries.length, 1);
  assert.equal(deliveries[0].body.source, "Kiroshi");
  assert.equal(deliveries[0].headers.cookie, undefined);
  assert.equal(deliveries[0].headers.authorization, undefined);
  assert.ok(deliveries[0].headers["user-agent"].includes("Mozilla/"));
  await evaluate(
    "document.querySelector('[data-action=refresh-performance]').click()",
  );
  await wait(
    "document.querySelector('#performance-summary')?.textContent.includes('Dashboard memory')",
  );
  await page("Performance.enable");
  const heap = await page("Performance.getMetrics");
  const usedHeap = heap.metrics.find(
    (metric) => metric.name === "JSHeapUsedSize",
  )?.value;
  if (usedHeap)
    console.log(`Browser JS heap: ${(usedHeap / 1048576).toFixed(2)} MB`);
  await evaluate(
    "document.querySelector('[data-action=remove-notification]').click()",
  );
  await wait("state.notifications.configured===false");
  await page("Emulation.setDeviceMetricsOverride", {
    width: 390,
    height: 844,
    deviceScaleFactor: 1,
    mobile: true,
  });
  await evaluate("document.querySelector('[data-view=\"overview\"]').click()");
  await evaluate(
    "new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))",
  );
  assert.equal(
    await evaluate("document.documentElement.scrollWidth <= window.innerWidth"),
    true,
  );
  const mobile = await page("Page.captureScreenshot", {
    format: "png",
    captureBeyondViewport: true,
  });
  await writeFile(
    "/tmp/kiroshi-mobile.png",
    Buffer.from(mobile.data, "base64"),
  );
  console.log(
    "PASS browser: overview, engagements, sessions, command previews, handoff, tools, report readiness gate, confirmed review, reference dialogs, live tool output, rerun identity, ordered workflows, loading/error recovery, confirmed history erasure, private webhook configuration and delivery, performance panel, mobile layout",
  );
  console.log(
    "Screenshots: /tmp/kiroshi-overview.png and /tmp/kiroshi-mobile.png",
  );
  await cdp("Browser.close").catch(() => {});
} finally {
  webhookReceiver?.close();
  chrome?.kill("SIGKILL");
  server.kill("SIGINT");
  await new Promise((resolve) => setTimeout(resolve, 800));
  await rm(directory, { recursive: true, force: true });
}
