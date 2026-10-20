#!/usr/bin/env node
// Isolated browser executor. No provider credentials, clients or model context.
const fs = require("fs"),
  path = require("path"),
  http = require("http"),
  crypto = require("crypto");
const { createRequire } = require("module");
const deps =
  process.env.AUDIENCE_NODE_MODULES ||
  path.resolve(__dirname, "../../node_modules");
const load = createRequire(path.join(deps, "_session_loader.cjs"));
const { chromium } = load("playwright");
const hash = (p) =>
  crypto.createHash("sha256").update(fs.readFileSync(p)).digest("hex");
class Executor {
  async init(config) {
    this.config = config;
    this.out = config.out;
    this.n = 0;
    this.errors = [];
    this.viewer = null;
    const site = path.resolve(config.bundle, "site"),
      extra = path.resolve(config.out, "gif-media");
    this.server = http.createServer((req, res) => {
      const url = new URL(req.url, "http://local");
      const isExtra = url.pathname.startsWith("/gif-media/");
      const root = isExtra ? extra : site;
      const rel = isExtra
        ? url.pathname.slice("/gif-media/".length)
        : url.pathname.slice(1) || "index.html";
      const file = path.resolve(root, decodeURIComponent(rel));
      if (
        !file.startsWith(root + path.sep) ||
        !fs.existsSync(file) ||
        !fs.statSync(file).isFile()
      ) {
        res.writeHead(404);
        res.end();
        return;
      }
      const types = {
        ".html": "text/html",
        ".css": "text/css",
        ".png": "image/png",
        ".svg": "image/svg+xml",
        ".jpg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".mp4": "video/mp4",
        ".ttf": "font/ttf",
      };
      const size = fs.statSync(file).size;
      const headers = {
        "Content-Type": types[path.extname(file)] || "application/octet-stream",
        "Accept-Ranges": "bytes",
        "Cache-Control": "no-store",
      };
      let start = 0,
        end = size - 1;
      if (req.headers.range) {
        const match = /^bytes=(\d+)-(\d*)$/.exec(req.headers.range);
        if (!match) {
          res.writeHead(416);
          res.end();
          return;
        }
        start = Number(match[1]);
        if (match[2]) end = Number(match[2]);
        end = Math.min(end, size - 1);
        if (start > end) {
          res.writeHead(416);
          res.end();
          return;
        }
        headers["Content-Range"] = `bytes ${start}-${end}/${size}`;
        res.writeHead(206, { ...headers, "Content-Length": end - start + 1 });
      } else res.writeHead(200, { ...headers, "Content-Length": size });
      fs.createReadStream(file, { start, end }).pipe(res);
    });
    await new Promise((resolve) => this.server.listen(0, "127.0.0.1", resolve));
    this.origin = `http://127.0.0.1:${this.server.address().port}`;
    const exe = process.env.BUNDLE_CHROMIUM_PATH;
    this.browser = await chromium.launch({
      headless: true,
      executablePath: exe,
      args: ["--mute-audio"],
    });
    this.context = await this.browser.newContext({
      viewport: { width: 1440, height: 900 },
      deviceScaleFactor: 1,
    });
    await this.context.route("**/*", (route) =>
      new URL(route.request().url()).origin === this.origin
        ? route.continue()
        : route.abort(),
    );
    this.page = await this.context.newPage();
    this.page.on("pageerror", (e) => this.errors.push(String(e)));
    await this.page.goto(this.origin, { waitUntil: "networkidle" });
    await this.page.evaluate(async (gifs) => {
      await document.fonts.ready;
      for (const g of gifs) {
        for (const img of document.querySelectorAll(
          `img[data-src-asset="${g.asset_id}"]`,
        )) {
          img.src = g.first_url;
          await img.decode();
          img.dataset.sessionGif = g.asset_id;
          const button = document.createElement("button");
          button.textContent = "Play one silent animation cycle";
          button.dataset.sessionGifButton = g.asset_id;
          img.insertAdjacentElement("afterend", button);
        }
      }
      let controlId = 0;
      for (const el of document.querySelectorAll("details,summary,button"))
        if (!el.dataset.blockId)
          el.dataset.blockId = "session-control-" + ++controlId;
      const mainEnd = [...document.querySelector("article").childNodes].find(
        (n) => n.nodeType === 8 && n.textContent.includes("MAIN_BODY_END"),
      );
      window.__sessionLastMain =
        mainEnd?.previousElementSibling?.dataset.blockId || null;
      window.__sessionMainReached = false;
      // Native UI playback cannot run during model latency.
      for (const v of document.querySelectorAll("video")) {
        v.pause();
        v.muted = true;
        v.defaultMuted = true;
        v.removeAttribute("autoplay");
      }
    }, config.gifs);
    return {
      browser: this.browser.version(),
      playwright: load("playwright/package.json").version,
      viewport: { width: 1440, height: 900 },
      condition: "desktop-muted-activated-motion",
      initial: await this.snapshot(),
    };
  }
  async snapshot() {
    const filename = `captures/view-${String(this.n++).padStart(3, "0")}.png`;
    fs.mkdirSync(path.join(this.out, "captures"), { recursive: true });
    const state = await this.page.evaluate(() => {
      function shown(el) {
        if (
          !el ||
          !el.checkVisibility({ checkVisibilityCSS: true, checkOpacity: true })
        )
          return false;
        if (el.closest("details:not([open])") && !el.closest("summary"))
          return false;
        const r = el.getBoundingClientRect();
        return (
          r.width > 0 &&
          r.height > 0 &&
          r.bottom > 0 &&
          r.top < innerHeight &&
          r.right > 0 &&
          r.left < innerWidth
        );
      }
      const overlay = document.getElementById("session-media-viewer");
      const texts = [];
      const walker = document.createTreeWalker(
        overlay || document.querySelector("article"),
        NodeFilter.SHOW_TEXT,
      );
      let n;
      while ((n = walker.nextNode())) {
        const parent = n.parentElement;
        if (!shown(parent) || ["SCRIPT", "STYLE"].includes(parent.tagName))
          continue;
        const range = document.createRange();
        range.selectNodeContents(n);
        const broad = range.getBoundingClientRect();
        if (broad.bottom <= 0 || broad.top >= innerHeight) continue;
        let current = "";
        let start = null;
        const pieces = [];
        for (let i = 0; i < n.textContent.length; i++) {
          range.setStart(n, i);
          range.setEnd(n, i + 1);
          const rr = range.getBoundingClientRect();
          const visible =
            rr.width > 0 &&
            rr.top >= 0 &&
            rr.bottom <= innerHeight &&
            rr.left >= 0 &&
            rr.right <= innerWidth;
          if (visible) {
            if (start === null) start = i;
            current += n.textContent[i];
          } else if (current) {
            pieces.push({ text: current, start, end: i });
            current = "";
            start = null;
          }
        }
        if (current)
          pieces.push({ text: current, start, end: n.textContent.length });
        const block = parent.closest("[data-block-id]");
        for (const piece of pieces)
          if (piece.text.trim()) {
            range.setStart(n, piece.start);
            range.setEnd(n, piece.end);
            texts.push({
              block_id: block?.dataset.blockId || "media-viewer",
              text: piece.text,
              visible_rects: [...range.getClientRects()].map((r) => ({
                x: r.x,
                y: r.y,
                width: r.width,
                height: r.height,
              })),
            });
          }
      }
      const targets = [];
      if (overlay) {
        targets.push({
          id: "viewer-close",
          kind: "close_media",
          label: "Return to article",
        });
      } else {
        for (const e of document.querySelectorAll("summary"))
          if (shown(e))
            targets.push({
              id: e.closest("details").dataset.blockId,
              kind: e.closest("details").open ? "collapse" : "expand",
              label: e.innerText,
            });
        for (const e of document.querySelectorAll("img[data-src-placement]"))
          if (shown(e))
            targets.push({
              id: e.dataset.srcPlacement,
              kind: "inspect_image",
              label: e.alt || "Image",
              asset_id: e.dataset.srcAsset,
            });
        for (const e of document.querySelectorAll("a[data-href-placement]"))
          if (shown(e))
            targets.push({
              id: e.dataset.hrefPlacement,
              kind: "open_media",
              label: e.innerText,
              asset_id: e.dataset.hrefAsset,
            });
        for (const e of document.querySelectorAll(
          "button[data-session-gif-button]",
        ))
          if (shown(e))
            targets.push({
              id: "gif-" + e.dataset.sessionGifButton,
              kind: "open_gif",
              label: e.textContent,
              asset_id: e.dataset.sessionGifButton,
            });
      }
      for (const e of document.querySelectorAll("video"))
        if (shown(e) && (overlay ? overlay.contains(e) : true))
          targets.push({
            id:
              e.id === "session-player"
                ? "viewer-player"
                : e.dataset.srcPlacement,
            kind: "player",
            label: "Muted video",
            asset_id: e.dataset.srcAsset || null,
            current_time: e.currentTime,
            duration: Number.isFinite(e.duration) ? e.duration : null,
            muted: e.muted,
            paused: e.paused,
            inline: !overlay,
          });
      // Only current visible fragments reveal the closing paragraph; no full-text or last-block ID is returned early.
      const final = window.__sessionLastMain;
      const el = final
        ? document.querySelector(`[data-block-id="${final}"]`)
        : null;
      if (!overlay && el && shown(el)) {
        const full = el.innerText.replace(/\s/g, "");
        const got = texts
          .filter((x) => x.block_id === final)
          .map((x) => x.text)
          .join("")
          .replace(/\s/g, "");
        if (got.length >= full.length * 0.9) window.__sessionMainReached = true;
      }
      return {
        scroll: { x: scrollX, y: scrollY },
        viewport: { width: innerWidth, height: innerHeight },
        texts,
        targets,
        closing_main_reached: window.__sessionMainReached,
        overlay: Boolean(overlay),
      };
    });
    await this.page.screenshot({
      path: path.join(this.out, filename),
      animations: "disabled",
    });
    state.screenshot = {
      path: filename,
      sha256: hash(path.join(this.out, filename)),
    };
    state.browser_errors = this.errors.length;
    this.last = state;
    return state;
  }
  async action(a) {
    const before = this.last;
    let error = null,
      success = false,
      playback = null,
      frames = [];
    const target = before.targets.find((x) => x.id === a.target);
    try {
      if (
        [
          "expand",
          "collapse",
          "inspect_image",
          "open_media",
          "open_gif",
          "play",
          "read_while_playing",
          "seek",
          "pause",
          "close_media",
        ].includes(a.action) &&
        !target
      )
        throw Error("Target not currently visible/available");
      if (a.action === "read") {
      } else if (["scroll_next", "scroll_back", "skip"].includes(a.action)) {
        if (before.overlay) throw Error("Close media before scrolling article");
        await this.page.evaluate(
          (d) => scrollBy(0, d),
          a.action === "scroll_back" ? -720 : 720,
        );
      } else if (["expand", "collapse"].includes(a.action)) {
        if (target.kind !== a.action) throw Error("Wrong disclosure state");
        await this.page
          .locator(`[data-block-id="${a.target}"] > summary`)
          .click();
      } else if (
        ["inspect_image", "open_media", "open_gif"].includes(a.action)
      ) {
        if (target.kind !== a.action) throw Error("Wrong target type");
        const manifest = this.config.assets.find(
          (x) => x.asset_id === target.asset_id,
        );
        if (!manifest) throw Error("Unknown local media");
        const gif = this.config.gifs.find(
          (x) => x.asset_id === target.asset_id,
        );
        const kind =
          manifest.mime_type.startsWith("image/") && !gif ? "img" : "video";
        const url = gif ? gif.video_url : manifest.site_url;
        await this.page.evaluate(
          ({ url, kind, asset }) => {
            const wrap = document.createElement("div");
            wrap.id = "session-media-viewer";
            Object.assign(wrap.style, {
              position: "fixed",
              inset: "0",
              zIndex: 9999,
              background: "#111",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
            });
            const label = document.createElement("div");
            label.textContent =
              "Media inspection — return to article when finished";
            label.style.color = "white";
            wrap.append(label);
            const media = document.createElement(kind);
            media.id = "session-player";
            media.dataset.srcAsset = asset;
            media.src = url;
            Object.assign(media.style, {
              maxWidth: "96vw",
              maxHeight: "82vh",
              width: "auto",
              height: "auto",
            });
            if (kind === "video") {
              media.muted = true;
              media.defaultMuted = true;
              media.controls = true;
              media.preload = "metadata";
            }
            wrap.append(media);
            document.body.append(wrap);
          },
          { url, kind, asset: target.asset_id },
        );
        await this.page.locator("#session-player").evaluate(async (e) => {
          if (e.tagName === "IMG") await e.decode();
          else if (e.readyState < 1) {
            if (e.error) throw Error("Media decode failed");
            await new Promise((resolve, reject) => {
              const finish = (error) => {
                clearTimeout(timer);
                e.removeEventListener("loadedmetadata", loaded);
                e.removeEventListener("error", failed);
                error ? reject(error) : resolve();
              };
              const loaded = () => finish();
              const failed = () => finish(Error("Media decode failed"));
              const timer = setTimeout(() => finish(Error("Media metadata timeout")), 5000);
              e.addEventListener("loadedmetadata", loaded, { once: true });
              e.addEventListener("error", failed, { once: true });
            });
          }
        });
      } else if (a.action === "close_media") {
        if (!before.overlay || target.kind !== "close_media")
          throw Error("No open media/close control");
        await this.page
          .locator("#session-media-viewer")
          .evaluate((e) => e.remove());
      } else if (
        ["play", "read_while_playing", "seek", "pause"].includes(a.action)
      ) {
        if (target.kind !== "player") throw Error("Not a player");
        if (a.action === "read_while_playing" && !target.inline)
          throw Error("Reading overlap requires inline article player");
        const locator =
          a.target === "viewer-player"
            ? this.page.locator("#session-player")
            : this.page.locator(`[data-src-placement="${a.target}"]`);
        if (a.action === "seek") {
          if (
            !(
              a.source_seconds >= 0 &&
              target.duration !== null &&
              a.source_seconds <= target.duration
            )
          )
            throw Error("Seek outside source interval");
          await locator.evaluate(async (v, t) => {
            v.pause();
            if (Math.abs(v.currentTime - t) < 0.01) return;
            await new Promise((resolve, reject) => {
              const timeout = setTimeout(() => {
                v.removeEventListener("seeked", done);
                reject(Error("Seek did not complete"));
              }, 5000);
              const done = () => {
                clearTimeout(timeout);
                resolve();
              };
              v.addEventListener("seeked", done, { once: true });
              v.currentTime = t;
            });
            if (Math.abs(v.currentTime - t) > 0.15)
              throw Error("Seek position mismatch");
          }, a.source_seconds);
        } else if (a.action === "pause") {
          if (target.paused) throw Error("Player already paused");
          await locator.evaluate((v) => v.pause());
        } else {
          if (!(a.seconds > 0 && a.seconds <= 4))
            throw Error("Playback outside bounded duration");
          const start = await locator.evaluate((v) => {
            v.muted = true;
            return v.currentTime;
          });
          await locator.evaluate((v) => v.play());
          const until = Date.now() + a.seconds * 1000;
          while (Date.now() < until) {
            await this.page.waitForTimeout(Math.min(1000, until - Date.now()));
            const t = await locator.evaluate((v) => v.currentTime);
            const f = `captures/play-${this.n++}.jpg`;
            await locator.screenshot({
              path: path.join(this.out, f),
              type: "jpeg",
              quality: 80,
            });
            frames.push({
              path: f,
              sha256: hash(path.join(this.out, f)),
              source_time: t,
              asset_id: target.asset_id,
            });
            if (await locator.evaluate((v) => v.ended)) break;
          }
          const end = await locator.evaluate((v) => {
            v.pause();
            return v.currentTime;
          });
          playback = {
            asset_id: target.asset_id,
            start,
            end,
            advanced_seconds: Math.max(0, end - start),
            muted: true,
            actual_sample_timestamps: frames.map((f) => f.source_time),
          };
        }
      } else if (a.action === "finish") {
        if (!before.closing_main_reached)
          throw Error("Closing main paragraph not reached");
      } else if (a.action !== "abandon") throw Error("Unknown action");
      success = true;
    } catch (e) {
      error = String(e.message || e);
    }
    await this.page.evaluate(() =>
      document.querySelectorAll("video").forEach((v) => {
        v.pause();
        v.muted = true;
      }),
    );
    const after = await this.snapshot();
    return { success, error, before, after, playback, frames };
  }
  async close() {
    await this.context?.close();
    await this.browser?.close();
    if (this.server) await new Promise((resolve) => this.server.close(resolve));
  }
}
module.exports = { Executor };
if (require.main === module) {
  const readline = require("readline");
  const ex = new Executor();
  (async () => {
    for await (const line of readline.createInterface({
      input: process.stdin,
    })) {
      try {
        const cmd = JSON.parse(line);
        let value;
        if (cmd.command === "init") value = await ex.init(cmd.config);
        else if (cmd.command === "snapshot") value = await ex.snapshot();
        else if (cmd.command === "action") value = await ex.action(cmd.action);
        else if (cmd.command === "close") {
          await ex.close();
          console.log(JSON.stringify({ ok: true }));
          process.stdin.destroy();
          break;
        } else throw Error("Unknown RPC command");
        console.log(JSON.stringify({ ok: true, value }));
      } catch (e) {
        console.log(
          JSON.stringify({ ok: false, error: String(e.message || e) }),
        );
      }
    }
  })().catch(async (e) => {
    console.error(String(e));
    await ex.close();
    process.exitCode = 1;
  });
}
