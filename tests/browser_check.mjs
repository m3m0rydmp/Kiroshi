// Optional Chrome smoke test using its native DevTools pipe; no npm dependencies.
import { spawn } from "node:child_process";
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
let chrome;
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
  await evaluate(
    `(()=>{const f=document.querySelector('#engagement-form');f.elements.name.value='Local lab / UI check';f.elements.scope.value='127.0.0.1';f.elements.policy.value='Loopback fixture only';f.elements.authorized.checked=true;f.requestSubmit();})()`,
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
    "PASS browser: overview, engagements, sessions, command previews, handoff, tools, report readiness gate, confirmed review, reference dialogs, mobile layout",
  );
  console.log(
    "Screenshots: /tmp/kiroshi-overview.png and /tmp/kiroshi-mobile.png",
  );
  await cdp("Browser.close").catch(() => {});
} finally {
  chrome?.kill("SIGKILL");
  server.kill("SIGINT");
  await new Promise((resolve) => setTimeout(resolve, 800));
  await rm(directory, { recursive: true, force: true });
}
