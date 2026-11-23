// 临时脚本：Edge headless + CDP 验证 P41「← 返回上一级」（不进入仓库运行时）。
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const EDGE = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const BASE = "http://127.0.0.1:8517";
const OUT = path.resolve("docs/evidence/P41-back-button-2026-11-22");
const PORT = 9223;
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

async function clickCard(cdp, label) {
  const r = await ev(
    cdp,
    `(()=>{const p=[...document.querySelectorAll("p")].find(x=>x.innerText.trim()===${JSON.stringify(label)});
      if(!p) return "nolabel";
      let n=p;
      for(let i=0;i<12 && n;i++){
        if(n.querySelector && n.querySelector("button")){ n.querySelector("button").click(); return "ok"; }
        n=n.parentElement;
      }
      return "nobtn";})()`,
  );
  if (r !== "ok") throw new Error("card " + label + " -> " + r);
}

// 量四件事：返回按钮的 rect / disabled，侧栏右边界，按钮是否落在分界线右侧的页首。
async function probe(cdp, tag) {
  const info = await ev(
    cdp,
    `(()=>{
      const all=[...document.querySelectorAll("button")].filter(b=>b.innerText.includes("返回上一级"));
      const back=all.filter(b=>b.getBoundingClientRect().width>0)[0];
      const sb=document.querySelector('section[data-testid="stSidebar"]');
      const rb=back?back.getBoundingClientRect():null;
      const rs=sb?sb.getBoundingClientRect():null;
      return {
        matches: all.length,
        hasBack: !!back,
        backText: back?back.innerText.trim():null,
        backDisabled: back?back.disabled:null,
        backTop: rb?Math.round(rb.top):null,
        backLeft: rb?Math.round(rb.left):null,
        sidebarRight: rs?Math.round(rs.right):null,
        backRightOfDivider: rb&&rs ? rb.left >= rs.right-2 : null,
        backNearTop: rb ? rb.top < 200 : null,
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
  await cdp.send("Page.navigate", { url: BASE + "/?u=p41" });
  if (!(await waitText(cdp, "今天想怎么待一会儿？"))) throw new Error("home not loaded");
  // 侧栏与主区不是同一批 delta，等按钮真的进 DOM 再量位置。
  if (!(await waitText(cdp, "返回上一级", 15000))) throw new Error("sidebar not rendered");
  await sleep(1200);
}

async function main() {
  const profile = path.resolve("docs/evidence/_p41_edge_profile");
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

    // ① 首页：按钮在分界线右侧的页首，处于禁用态。
    await home(cdp);
    const p1 = await probe(cdp, "home");
    assert(p1.hasBack, "home 没有返回按钮");
    assert(p1.backDisabled === true, "首页按钮应为禁用");
    assert(p1.backRightOfDivider === true, "按钮必须在侧栏分界线右侧");
    assert(p1.backNearTop === true, "按钮必须在页首");
    await shot(cdp, "01-home-back-disabled.png");

    // ② 危难页（用户截图那张）：按钮可用。
    await clickText(cdp, "我现在很难受");
    assert(await waitText(cdp, "先打这一个"), "没进 help/self");
    await sleep(600);
    const p2 = await probe(cdp, "help-self");
    assert(p2.backDisabled === false, "help 页按钮应可用");
    assert(p2.backRightOfDivider === true, "help 页按钮仍在分界线右侧");
    await shot(cdp, "02-help-self-back-enabled.png");

    // ③ 点返回 → 回到首页，按钮重新禁用。
    await clickText(cdp, "← 返回上一级");
    assert(await waitText(cdp, "今天想怎么待一会儿？"), "返回后没回首页");
    await sleep(600);
    const p3 = await probe(cdp, "after-back");
    assert(p3.backDisabled === true, "回首页后按钮应禁用");
    await shot(cdp, "03-back-to-home.png");

    // ④ 两级路径：首页 → 索引 → 睡不着 → 返回应是索引，不是首页。
    await clickText(cdp, "我遇到一件具体的事");
    assert(await waitText(cdp, "18 个时刻"), "没进索引页");
    await sleep(500);
    await shot(cdp, "04-index.png");
    await clickCard(cdp, "躺下睡不着，脑子停不下来");
    assert(await waitText(cdp, "困了再回床上"), "没进睡不着页");
    await sleep(500);
    await shot(cdp, "05-sleep.png");
    await clickText(cdp, "← 返回上一级");
    assert(await waitText(cdp, "18 个时刻"), "返回后没回索引页");
    await sleep(500);
    await probe(cdp, "after-back-index");
    await shot(cdp, "06-back-to-index.png");
    await clickText(cdp, "← 返回上一级");
    assert(await waitText(cdp, "今天想怎么待一会儿？"), "第二次返回没回首页");
    await sleep(500);
    await shot(cdp, "07-back-home-again.png");

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
