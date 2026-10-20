// Authored browser mechanics probes. No provider credentials or inference.
const assert = require("node:assert/strict"),
  fs = require("node:fs"),
  path = require("node:path"),
  os = require("node:os"),
  cp = require("node:child_process");
const { Executor } = require("../engine/session/browser_rpc.cjs");
const root = path.resolve(__dirname, ".."),
  temp = fs.mkdtempSync(path.join(os.tmpdir(), "audience-sim-"));
const env = {
  ...process.env,
  PYTHONPATH: path.join(root, "engine"),
  PYTHONDONTWRITEBYTECODE: "1",
};
function py(...args) {
  return cp.execFileSync("python3", args, { cwd: root, env, encoding: "utf8" });
}
(async () => {
  const bundle = path.join(temp, "bundle"),
    prepared = path.join(temp, "prepared"),
    out = path.join(temp, "probe");
  py(
    "engine/bundle.py",
    "--article",
    "examples/article-a.json",
    "--out",
    bundle,
  );
  py(
    "engine/session/session_reader.py",
    "prepare",
    "--bundle",
    bundle,
    "--out",
    prepared,
    "--model",
    "authored-fixture",
  );
  fs.mkdirSync(out);
  fs.symlinkSync(
    path.join(prepared, "gif-media"),
    path.join(out, "gif-media"),
    "dir",
  );
  const config = {
    ...JSON.parse(fs.readFileSync(path.join(prepared, "config.json"))),
    out,
  };
  const ex = new Executor(),
    checks = [];
  try {
    const initial = await ex.init(config);
    assert(!initial.initial.closing_main_reached);
    assert(
      !JSON.stringify(initial.initial).includes("OPTIONAL_FIXTURE_SENTINEL"),
    );
    checks.push("Opening does not reveal closing or optional body");
    await ex.page.evaluate(() => {
      const p = document.createElement("p");
      p.style.marginTop = "6000px";
      p.textContent = "FUTURE_ONLY_SENTINEL";
      document.querySelector("article").append(p);
    });
    const snap = await ex.snapshot();
    assert(!JSON.stringify(snap).includes("FUTURE_ONLY_SENTINEL"));
    checks.push("Offscreen characters withheld");
    assert(
      !(
        await ex.action({
          action: "expand",
          target: "not-current",
          seconds: 0,
          source_seconds: null,
        })
      ).success,
    );
    checks.push("Unknown targets rejected");
    assert(
      !(
        await ex.action({
          action: "finish",
          target: null,
          seconds: 0,
          source_seconds: null,
        })
      ).success,
    );
    checks.push("Premature finish rejected");
    await ex.page
      .locator("a[data-href-placement]")
      .evaluate((e) => e.scrollIntoView({ block: "center" }));
    await ex.snapshot();
    const link = ex.last.targets.find((t) => t.kind === "open_media");
    assert(link);
    assert(
      (
        await ex.action({
          action: "open_media",
          target: link.id,
          seconds: 0,
          source_seconds: null,
        })
      ).success,
    );
    checks.push("Visible source clip opens");
    const played = await ex.action({
      action: "play",
      target: "viewer-player",
      seconds: 0.7,
      source_seconds: null,
    });
    assert(
      played.success &&
        played.playback.advanced_seconds > 0 &&
        played.playback.muted,
    );
    checks.push("Muted playback measures source interval");
    const seek = await ex.action({
      action: "seek",
      target: "viewer-player",
      seconds: 0,
      source_seconds: 2,
    });
    assert(seek.success);
    assert(
      Math.abs(
        seek.after.targets.find((t) => t.id === "viewer-player").current_time -
          2,
      ) < 0.2,
    );
    checks.push("Byte-range seek reaches declared source time");
    assert(
      !(
        await ex.action({
          action: "read_while_playing",
          target: "viewer-player",
          seconds: 1,
          source_seconds: null,
        })
      ).success,
    );
    checks.push("Occluded reading overlap rejected");
    assert(
      (
        await ex.action({
          action: "close_media",
          target: "viewer-close",
          seconds: 0,
          source_seconds: null,
        })
      ).success,
    );
    const gifId = config.gifs[0].asset_id;
    await ex.page
      .locator("button[data-session-gif-button]")
      .evaluate((e) => e.scrollIntoView({ block: "center" }));
    await ex.snapshot();
    assert(
      (
        await ex.action({
          action: "open_gif",
          target: "gif-" + gifId,
          seconds: 0,
          source_seconds: null,
        })
      ).success,
    );
    const gif = await ex.action({
      action: "play",
      target: "viewer-player",
      seconds: 0.7,
      source_seconds: null,
    });
    assert(gif.success && gif.playback.advanced_seconds > 0);
    const time = gif.after.targets.find(
      (t) => t.id === "viewer-player",
    ).current_time;
    await ex.page.waitForTimeout(200);
    assert(
      Math.abs(
        (await ex.snapshot()).targets.find((t) => t.id === "viewer-player")
          .current_time - time,
      ) < 0.02,
    );
    checks.push("Activated GIF is paused during decision latency");
    await ex.action({
      action: "close_media",
      target: "viewer-close",
      seconds: 0,
      source_seconds: null,
    });
    await ex.page
      .locator("details > summary")
      .evaluate((e) => e.scrollIntoView({ block: "center" }));
    await ex.snapshot();
    const details = ex.last.targets.find((t) => t.kind === "expand");
    assert(details);
    assert(
      (
        await ex.action({
          action: "expand",
          target: details.id,
          seconds: 0,
          source_seconds: null,
        })
      ).success,
    );
    assert(
      (
        await ex.action({
          action: "collapse",
          target: details.id,
          seconds: 0,
          source_seconds: null,
        })
      ).success,
    );
    checks.push("Disclosure exposure follows executed action");
    await ex.page
      .locator('[data-block-id="closing"]')
      .evaluate((e) => e.scrollIntoView({ block: "center" }));
    await ex.snapshot();
    assert(ex.last.closing_main_reached);
    assert(
      (
        await ex.action({
          action: "finish",
          target: null,
          seconds: 0,
          source_seconds: null,
        })
      ).success,
    );
    checks.push("Main-post finish does not require optional methods");
  } finally {
    await ex.close();
  }
  // Full authored-policy trace through the same request contract and independent auditor.
  py("engine/session/session_reader.py", "fixture-run", "--out", prepared);
  assert(!fs.existsSync(path.join(prepared, "browser-close-error.json")));
  checks.push("Authored session RPC shuts down without a close timeout");
  const audit = JSON.parse(py("engine/session/audit.py", "--out", prepared));
  assert.equal(audit.status, "verified_authored_trace_not_a_simulated_read");
  assert.equal(audit.provider_calls, 0);
  assert.equal(audit.model_calls, 0);
  assert(audit.contract_turns > 0);
  checks.push("Audited authored trace never becomes a model-simulated read");
  const capped = path.join(temp, "capped");
  py(
    "engine/session/session_reader.py",
    "prepare",
    "--bundle",
    bundle,
    "--out",
    capped,
    "--model",
    "authored-fixture",
    "--max-decisions",
    "1",
  );
  py("engine/session/session_reader.py", "fixture-run", "--out", capped);
  assert(!fs.existsSync(path.join(capped, "browser-close-error.json")));
  checks.push("Capped session RPC shuts down without a close timeout");
  const capAudit = JSON.parse(py("engine/session/audit.py", "--out", capped));
  assert(
    capAudit.cap_censored &&
      !capAudit.completed_main &&
      capAudit.provider_calls === 0,
  );
  checks.push("Action cap preserves censoring instead of completion");
  const config2 = { ...config, out: path.join(temp, "reset") };
  fs.mkdirSync(config2.out);
  const clean = new Executor();
  try {
    const reset = await clean.init(config2);
    assert.equal(reset.initial.scroll.y, 0);
    assert(!reset.initial.overlay);
    assert(!JSON.stringify(reset.initial).includes("FUTURE_ONLY_SENTINEL"));
    checks.push("Fresh browser context has no cross-session state");
  } finally {
    await clean.close();
  }
  const report = {
    kind: "authored_browser_mechanics_only",
    provider_calls: 0,
    checks_passed: checks.length,
    checks,
  };
  fs.writeFileSync(
    path.join(temp, "report.json"),
    JSON.stringify(report, null, 2),
  );
  console.log(
    JSON.stringify(
      { ...report, local_report: path.join(temp, "report.json") },
      null,
      2,
    ),
  );
})().catch((e) => {
  console.error(e.stack);
  process.exitCode = 1;
});
