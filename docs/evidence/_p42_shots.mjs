// 临时脚本：Edge headless + CDP 验证 P42「与心屿交流一下」侧栏常驻入口（不进运行时）。
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const EDGE = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const BASE = "http://127.0.0.1:8517";
const OUT = path.resolve("docs/evidence/P42-talk-entry-2026-11-22");
const PORT = 9224;
const W = 1360;
const H = 920;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

fs.mkdirSync(OUT, { recursive: true });

async function waitHttp(url, timeout = 25000) {
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

async function waitText(cdp, text, timeout = 20000) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeout) {
    const ok = await ev(cdp, `!!(document.body && document.body.innerText.includes(${JSON.stringify(text)}))`);
    if (ok) return true;
    await sleep(350);
  }
  return false;
}

async function waitSel(cdp, sel, timeout = 20000) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeout) {
    const ok = await ev(cdp, `!!document.querySelector(${JSON.stringify(sel)})`);
    if (ok) return true;
    await sleep(350);
  }
  return false;
}

async function shot(cdp, name) {
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

// 量：入口在不在、是否禁用、是否在侧栏内、是否排在配色之上。
async function probe(cdp, tag) {
  const info = await ev(
    cdp,
    `(()=>{
      const all=[...document.querySelectorAll("button")].filter(b=>b.innerText.trim()==="与心屿交流一下" && b.getBoundingClientRect().width>0);
      const t=all[0];
      const sb=document.querySelector('section[data-testid="stSidebar"]');
      const radio=document.querySelector('[data-testid="stRadio"]');
      const tr=t?t.getBoundingClientRect():null;
      const sr=sb?sb.getBoundingClientRect():null;
      const rr=radio?radio.getBoundingClientRect():null;
      return {
        matches: all.length,
        hasTalk: !!t,
        talkText: t?t.innerText.trim():null,
        talkDisabled: t?t.disabled:null,
        talkTop: tr?Math.round(tr.top):null,
        talkLeft: tr?Math.round(tr.left):null,
        sidebarLeft: sr?Math.round(sr.left):null,
        sidebarRight: sr?Math.round(sr.right):null,
        inSidebar: tr&&sr ? (tr.left >= sr.left-2 && tr.right <= sr.right+2) : null,
        themeTop: rr?Math.round(rr.top):null,
        talkAboveTheme: tr&&rr ? tr.top < rr.top : null,
        hasChatInput: !!document.querySelector('[data-testid="stChatInput"] textarea'),
        hasBack: [...document.querySelectorAll("button")].some(b=>b.innerText.includes("返回上一级") && b.getBoundingClientRect().width>0),
        backTop: (()=>{const b=[...document.querySelectorAll("button")].filter(x=>x.innerText.includes("返回上一级") && x.getBoundingClientRect().width>0)[0]; return b?Math.round(b.getBoundingClientRect().top):null;})(),
      };
    })()`,
  );
  console.log("probe", tag, JSON.stringify(info));
  return info;
}

function assert(cond, msg) {
  if (!cond) throw new Error("ASSERT " + msg);
}

async function home(cdp) {
  await cdp.send("Page.navigate", { url: BASE + "/?u=p42" });
  if (!(await waitText(cdp, "今天想怎么待一会儿？"))) throw new Error("home not loaded");
  if (!(await waitText(cdp, "与心屿交流一下", 15000))) throw new Error("sidebar talk not rendered");
  await sleep(1200);
}

async function main() {
  const profile = path.resolve("docs/evidence/_p42_edge_profile");
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

    // ① 首页：侧栏第一项是它，配色在下面，可点。
    await home(cdp);
    const p1 = await probe(cdp, "home");
    assert(p1.hasTalk, "首页侧栏没有入口");
    assert(p1.talkDisabled === false, "首页入口应可点");
    assert(p1.inSidebar === true, "入口必须在侧栏里");
    assert(p1.talkAboveTheme === true, "入口应排在配色之上");
    await shot(cdp, "01-home-sidebar-talk.png");

    // ② 危难页：入口不随页面消失，位置不动。
    await clickText(cdp, "我现在很难受");
    assert(await waitText(cdp, "先打这一个"), "没进 help/self");
    await sleep(700);
    const p2 = await probe(cdp, "help-self");
    assert(p2.hasTalk, "help 页入口消失了");
    assert(p2.talkDisabled === false, "help 页入口应可点");
    assert(p2.talkTop === p1.talkTop, "入口位置不应随页面移动");
    await shot(cdp, "02-help-self-sidebar-talk.png");

    // ③ 点它 → 陪伴模式；入口仍在，但显示为已在这里。
    await clickText(cdp, "与心屿交流一下");
    assert(await waitSel(cdp, '[data-testid="stChatInput"] textarea'), "没进陪伴模式");
    await sleep(700);
    // Streamlit 的滚动容器是内部 div，window.scrollTo 不管用；把所有能滚的都回顶。
    await ev(
      cdp,
      `(()=>{window.scrollTo(0,0);
        [...document.querySelectorAll("*")].forEach(el=>{ if (el.scrollTop) el.scrollTop=0; });
        return true;})()`,
    );
    await sleep(500);
    const p3 = await probe(cdp, "companion");
    assert(p3.hasTalk, "陪伴模式里入口应保留");
    assert(p3.talkDisabled === true, "已在陪伴模式时应禁用");
    assert(p3.hasBack === true, "陪伴模式里返回按钮仍应在页首");
    assert(p3.backTop !== null && p3.backTop >= 0 && p3.backTop < 200, "返回按钮应回到页首可见");
    await shot(cdp, "03-companion-talk-disabled.png");

    // ④ 返回键照常退回刚才那一页。
    await clickText(cdp, "← 返回上一级");
    assert(await waitText(cdp, "先打这一个"), "返回后没回 help/self");
    await sleep(600);
    const p4 = await probe(cdp, "back-to-help");
    assert(p4.talkDisabled === false, "回 help 后入口应恢复可点");
    await shot(cdp, "04-back-to-help.png");

    cdp.close();
  } finally {
    edge.kill();
    await sleep(800);
    fs.rmSync(profile, { recursive: true, force: true });
  }
  console.log("done");
}

main().catch((e) => {
  console.error("FAIL", e);
  process.exit(1);
});
