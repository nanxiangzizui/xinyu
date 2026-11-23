// P47 临时验收：材料改版用的界面截图（首页 / 索引 / 危机页 / 聊天 / 问卷 / 角色卡门）。
// 只用于 docs/evidence 取图，不进运行时。
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const EDGE = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const BASE = "http://127.0.0.1:8517";
const OUT = path.resolve("docs/evidence/P47-materials-2026-11-23");
const PORT = 9227;
const W = 1360;
const H = 1020;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

fs.mkdirSync(OUT, { recursive: true });

async function waitHttp(url, timeout = 40000) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeout) {
    try {
      const r = await fetch(url);
      if (r.ok) return true;
    } catch {}
    await sleep(400);
  }
  throw new Error("http timeout " + url);
}

class CDP {
  constructor(ws) {
    this.ws = ws;
    this.id = 0;
    this.pending = new Map();
  }
  static async connect(url) {
    const ws = new WebSocket(url);
    const c = new CDP(ws);
    await new Promise((res, rej) => {
      ws.onopen = res;
      ws.onerror = () => rej(new Error("ws error"));
    });
    ws.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.id && c.pending.has(m.id)) {
        const { res, rej } = c.pending.get(m.id);
        c.pending.delete(m.id);
        m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result);
      }
    };
    return c;
  }
  send(method, params = {}) {
    const id = ++this.id;
    return new Promise((res, rej) => {
      this.pending.set(id, { res, rej });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }
  close() {
    this.ws.close();
  }
}

async function ev(cdp, expr) {
  const r = await cdp.send("Runtime.evaluate", {
    expression: expr,
    returnByValue: true,
    awaitPromise: true,
  });
  if (r.exceptionDetails) throw new Error("eval: " + r.exceptionDetails.text);
  return r.result.value;
}

async function waitText(cdp, text, timeout = 30000) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeout) {
    const ok = await ev(cdp, `!!(document.body && document.body.innerText.includes(${JSON.stringify(text)}))`);
    if (ok) return true;
    await sleep(350);
  }
  throw new Error("text not found: " + text);
}

async function waitEl(cdp, selector, timeout = 30000) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeout) {
    const ok = await ev(cdp, `!!document.querySelector(${JSON.stringify(selector)})`);
    if (ok) return true;
    await sleep(350);
  }
  throw new Error("element not found: " + selector);
}

async function scrollTop(cdp) {
  await ev(
    cdp,
    `(()=>{window.scrollTo(0,0);
      [...document.querySelectorAll("*")].forEach(el=>{ if (el.scrollTop) el.scrollTop=0; });
      return true;})()`,
  );
  await sleep(450);
}

async function shot(cdp, name) {
  await scrollTop(cdp);
  const r = await cdp.send("Page.captureScreenshot", {
    format: "png",
    fromSurface: true,
    captureBeyondViewport: false,
  });
  fs.writeFileSync(path.join(OUT, name), Buffer.from(r.data, "base64"));
  console.log("shot", name);
}

async function shotBottom(cdp, name) {
  await ev(
    cdp,
    `(()=>{[...document.querySelectorAll("div,section,main")].forEach(el=>{
        if (el.scrollHeight > el.clientHeight + 40) el.scrollTop = el.scrollHeight; });
      return true;})()`,
  );
  await sleep(700);
  const r = await cdp.send("Page.captureScreenshot", {
    format: "png",
    fromSurface: true,
    captureBeyondViewport: false,
  });
  fs.writeFileSync(path.join(OUT, name), Buffer.from(r.data, "base64"));
  console.log("shot", name);
}

async function clickText(cdp, text) {
  const ok = await ev(
    cdp,
    `(()=>{const b=[...document.querySelectorAll("button")].filter(x=>x.innerText.trim()===${JSON.stringify(text)} && x.getBoundingClientRect().width>0)[0];
      if(!b) return false; b.click(); return true;})()`,
  );
  if (!ok) throw new Error("no button " + text);
}

async function typeChat(cdp, text) {
  const box = await ev(
    cdp,
    `(()=>{const ta=[...document.querySelectorAll("textarea")].filter(x=>x.getBoundingClientRect().width>0).pop();
      if(!ta) return null; ta.focus();
      const btn=document.querySelector('[data-testid="stChatInputSubmitButton"]')||ta.closest("div").querySelector("button");
      const r=(btn||ta).getBoundingClientRect();
      return {x:Math.round(r.x+r.width/2), y:Math.round(r.y+r.height/2), hasBtn:!!btn};})()`,
  );
  if (!box) throw new Error("no chat textarea");
  await sleep(300);
  await cdp.send("Input.insertText", { text });
  await sleep(400);
  for (const type of ["mousePressed", "mouseReleased"]) {
    await cdp.send("Input.dispatchMouseEvent", {
      type, x: box.x, y: box.y, button: "left", clickCount: 1,
    });
  }
  await sleep(600);
}

async function countBubbles(cdp) {
  return ev(cdp, `document.querySelectorAll('[data-testid="stChatMessage"]').length`);
}

function assert(cond, msg) {
  if (!cond) throw new Error("ASSERT " + msg);
}

async function main() {
  const profile = path.resolve("docs/evidence/_p47_edge_profile");
  fs.rmSync(profile, { recursive: true, force: true });
  const edge = spawn(EDGE, [
    "--headless=new",
    "--disable-gpu",
    "--no-first-run",
    "--no-default-browser-check",
    `--remote-debugging-port=${PORT}`,
    `--user-data-dir=${profile}`,
    `--window-size=${W},${H}`,
    "about:blank",
  ]);
  try {
    await waitHttp(`http://127.0.0.1:${PORT}/json/version`);
    const t = await (await fetch(`http://127.0.0.1:${PORT}/json/new?url=about:blank`, { method: "PUT" })).json();
    const cdp = await CDP.connect(t.webSocketDebuggerUrl);
    await cdp.send("Page.enable");
    await cdp.send("Runtime.enable");
    await cdp.send("Emulation.setDeviceMetricsOverride", {
      width: W, height: H, deviceScaleFactor: 1, mobile: false,
    });

    // 01 首页
    await cdp.send("Page.navigate", { url: BASE + "/?u=p47" });
    await waitText(cdp, "今天想怎么待一会儿？");
    await sleep(1500);
    const home = await ev(
      cdp,
      `(()=>{const t=document.body.innerText;return {idx:t.includes("我遇到一件具体的事"),res:t.includes("86878592"),about:t.includes("关于心屿")};})()`,
    );
    assert(home.idx && home.res && home.about, "home incomplete " + JSON.stringify(home));
    await shot(cdp, "01-home.png");

    // 02 索引页
    await clickText(cdp, "我遇到一件具体的事");
    await waitText(cdp, "我遇到的是…");
    await waitText(cdp, "26 个入口");
    await sleep(1200);
    await shot(cdp, "02-index.png");

    // 03 危机页（索引第一张卡就是「我现在很难受」）
    const first = await ev(
      cdp,
      `(()=>{const b=[...document.querySelectorAll("button")].filter(x=>x.innerText.trim()==="去这里" && x.getBoundingClientRect().width>0)[0];
        if(!b) return false; b.click(); return true;})()`,
    );
    assert(first, "no 去这里 button");
    await waitText(cdp, "如果现在很危险");
    await waitText(cdp, "先打这一个");
    await sleep(1200);
    await shot(cdp, "03-crisis.png");

    // 04 聊天页（MOCK 剧本）
    await cdp.send("Page.navigate", { url: BASE + "/?u=p47b" });
    await waitText(cdp, "今天想怎么待一会儿？");
    await sleep(1500);
    const btns = await ev(
      cdp,
      `[...document.querySelectorAll("button")].filter(b=>b.getBoundingClientRect().width>0).map(b=>b.innerText.trim()).filter(Boolean)`,
    );
    console.log("home buttons", JSON.stringify(btns));
    await clickText(cdp, "我想说说");
    await waitEl(cdp, "textarea");
    await sleep(1500);
    await typeChat(cdp, "今天有点累，想安静一会儿。");
    await sleep(4000);
    await typeChat(cdp, "其实还有件事，说出来有点丢人。");
    await sleep(4500);
    const bubbles = await countBubbles(cdp);
    console.log("chat bubbles", bubbles);
    assert(bubbles >= 4, "chat did not submit, bubbles=" + bubbles);
    await shotBottom(cdp, "04-chat.png");

    // 05 问卷页（入口在侧栏最底部）
    await cdp.send("Page.navigate", { url: BASE + "/?u=p47" });
    await waitText(cdp, "今天想怎么待一会儿？");
    await clickText(cdp, "匿名问卷（帮我们做研究）");
    await waitText(cdp, "匿名问卷");
    await sleep(1200);
    await shot(cdp, "05-survey.png");

    // 06 角色卡免责门
    await cdp.send("Page.navigate", { url: BASE + "/?u=p47c" });
    await waitText(cdp, "今天想怎么待一会儿？");
    await sleep(2000);
    await clickText(cdp, "给心屿一张角色卡");
    await sleep(3500);
    const rc = await ev(cdp, `document.body.innerText.slice(0, 2000)`);
    console.log("rolecard page", JSON.stringify(rc.slice(0, 400)));
    await shot(cdp, "06-rolecard.png");

    cdp.close();
    console.log("done");
  } finally {
    edge.kill();
    await sleep(800);
    fs.rmSync(profile, { recursive: true, force: true });
  }
}

main().catch((e) => {
  console.error("FAIL", e);
  process.exit(1);
});
