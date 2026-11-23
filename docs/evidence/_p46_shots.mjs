// P46 临时验收：首页精简后的分组、页尾关于入口、随机入口已删（不进运行时）。
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const EDGE = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const BASE = "http://127.0.0.1:8517";
const OUT = path.resolve("docs/evidence/P46-home-condense-2026-11-23");
const PORT = 9226;
const W = 1360;
const H = 2400;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

fs.mkdirSync(OUT, { recursive: true });

async function waitHttp(url, timeout = 30000) {
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

async function waitText(cdp, text, timeout = 25000) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeout) {
    const ok = await ev(cdp, `!!(document.body && document.body.innerText.includes(${JSON.stringify(text)}))`);
    if (ok) return true;
    await sleep(350);
  }
  return false;
}

async function scrollTop(cdp) {
  await ev(
    cdp,
    `(()=>{window.scrollTo(0,0);
      [...document.querySelectorAll("*")].forEach(el=>{ if (el.scrollTop) el.scrollTop=0; });
      return true;})()`,
  );
  await sleep(500);
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

async function clickText(cdp, text) {
  const ok = await ev(
    cdp,
    `(()=>{const b=[...document.querySelectorAll("button")].filter(x=>x.innerText.trim()===${JSON.stringify(text)} && x.getBoundingClientRect().width>0)[0];
      if(!b) return false; b.click(); return true;})()`,
  );
  if (!ok) throw new Error("no button " + text);
}

async function probe(cdp, tag) {
  const info = await ev(
    cdp,
    `(()=>{
      const text=document.body.innerText;
      const strongs=[...document.querySelectorAll("strong")].map(e=>e.innerText.trim());
      const btns=[...document.querySelectorAll("button")].filter(b=>b.getBoundingClientRect().width>0).map(b=>b.innerText.trim());
      return {
        groups: ["先说说话","自己待一会儿","动动脑子，不费劲","去咨询 / 跟学校打交道"].map(t=>[t, strongs.includes(t)]),
        oldSchoolHeading: strongs.includes("要跟学校打交道时"),
        oldAboutHeading: strongs.includes("关于心屿"),
        aboutButton: btns.includes("关于心屿：它是什么、记了什么、怎么删"),
        randomButton: btns.some(t=>t.includes("随便")),
        cardButtons: btns.filter(t=>t==="进去看看").length,
        hasHelpSelf: btns.includes("我现在很难受"),
        hasTalk: btns.includes("我想说说"),
        hasResources: text.includes("12356") && text.includes("86878592"),
      };
    })()`,
  );
  console.log("probe", tag, JSON.stringify(info));
  return info;
}

function assert(cond, msg) {
  if (!cond) throw new Error("ASSERT " + msg);
}

async function main() {
  const profile = path.resolve("docs/evidence/_p46_edge_profile");
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

    await cdp.send("Page.navigate", { url: BASE + "/?u=p46" });
    if (!(await waitText(cdp, "今天想怎么待一会儿？"))) throw new Error("home not loaded");
    if (!(await waitText(cdp, "关于心屿：它是什么、记了什么、怎么删", 20000))) throw new Error("footer about not rendered");
    await sleep(1400);
    await shot(cdp, "01-home-condensed.png");

    const p = await probe(cdp, "home");
    p.groups.forEach(([title, ok]) => assert(ok, "missing group " + title));
    assert(!p.oldSchoolHeading, "old school heading still there");
    assert(!p.oldAboutHeading, "old about heading still there");
    assert(p.aboutButton, "footer about button missing");
    assert(!p.randomButton, "random button still there");
    assert(p.cardButtons === 0, "old card buttons " + p.cardButtons);
    assert(p.hasHelpSelf && p.hasTalk, "triage buttons missing");
    assert(p.hasResources, "crisis resources missing");

    // 页尾「关于心屿」仍能进同一张边界/数据页，返回键也能回来。
    await clickText(cdp, "关于心屿：它是什么、记了什么、怎么删");
    if (!(await waitText(cdp, "心屿是什么，不是什么"))) throw new Error("about page not loaded");
    await sleep(900);
    await shot(cdp, "02-about-from-footer.png");
    await clickText(cdp, "← 返回上一级");
    if (!(await waitText(cdp, "今天想怎么待一会儿？"))) throw new Error("back home failed");
    await sleep(700);
    console.log("probe back", JSON.stringify(await probe(cdp, "back-home")));

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
