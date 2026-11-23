// 临时脚本：Edge headless + CDP 验证 P43「页面内部不再有回首页」（不进运行时）。
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const EDGE = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const BASE = "http://127.0.0.1:8517";
const OUT = path.resolve("docs/evidence/P43-no-redundant-home-2026-11-22");
const PORT = 9225;
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

// 首页卡片：按钮文字都一样，只能从卡片标题往上找到那张卡自己的「进去看看」。
async function clickCard(cdp, cardTitle) {
  const ok = await ev(
    cdp,
    `(()=>{const label=[...document.querySelectorAll("p,strong,span,div")].find(e=>e.innerText.trim()===${JSON.stringify(cardTitle)});
      if(!label) return false;
      let p=label;
      for(let i=0;i<8&&p;i++,p=p.parentElement){
        const b=[...p.querySelectorAll("button")].find(x=>x.innerText.trim()==="进去看看");
        if(b){ b.click(); return true; }
      }
      return false;})()`,
  );
  if (!ok) throw new Error("no card " + cardTitle);
}

// 量：主区里还有没有「回首页」、侧栏有几个、页首返回键在不在。
async function probe(cdp, tag) {
  const info = await ev(
    cdp,
    `(()=>{
      const sb=document.querySelector('section[data-testid="stSidebar"]');
      const sr=sb?sb.getBoundingClientRect():null;
      const btns=[...document.querySelectorAll("button")].filter(b=>b.getBoundingClientRect().width>0);
      const homes=btns.filter(b=>b.innerText.trim()==="回首页");
      const inSidebar=(b)=>{const r=b.getBoundingClientRect(); return sr? (r.left>=sr.left-2 && r.right<=sr.right+2):false;};
      const mainHomes=homes.filter(b=>!inSidebar(b));
      const sideHomes=homes.filter(inSidebar);
      const back=btns.filter(b=>b.innerText.includes("返回上一级"))[0];
      return {
        mainHomeCount: mainHomes.length,
        mainHomeTexts: mainHomes.map(b=>b.innerText.trim()),
        sidebarHomeCount: sideHomes.length,
        hasBack: !!back,
        backDisabled: back?back.disabled:null,
        backTop: back?Math.round(back.getBoundingClientRect().top):null,
      };
    })()`,
  );
  console.log("probe", tag, JSON.stringify(info));
  return info;
}

function assert(cond, msg) {
  if (!cond) throw new Error("ASSERT " + msg);
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

async function expectPage(cdp, tag, shotName, waitFor) {
  if (waitFor && !(await waitText(cdp, waitFor))) throw new Error("page not loaded: " + tag);
  await sleep(800);
  await scrollTop(cdp);
  const p = await probe(cdp, tag);
  assert(p.mainHomeCount === 0, `${tag} 主区里还有回首页：${p.mainHomeTexts}`);
  assert(p.sidebarHomeCount === 1, `${tag} 侧栏回首页数量应为 1`);
  assert(p.hasBack === true, `${tag} 页首没有返回键`);
  await shot(cdp, shotName);
  return p;
}

async function backHome(cdp) {
  await clickText(cdp, "← 返回上一级");
  assert(await waitText(cdp, "今天想怎么待一会儿？"), "返回后没回首页");
  await sleep(600);
}

async function main() {
  const profile = path.resolve("docs/evidence/_p43_edge_profile");
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

    await cdp.send("Page.navigate", { url: BASE + "/?u=p43" });
    if (!(await waitText(cdp, "今天想怎么待一会儿？"))) throw new Error("home not loaded");
    if (!(await waitText(cdp, "与心屿交流一下", 15000))) throw new Error("sidebar not rendered");
    await sleep(1200);

    // ① 写下来：用户圈的就是这一页，页内不再有回首页，只剩页首返回键 + 侧栏出口。
    await clickCard(cdp, "写下来");
    await expectPage(cdp, "journal", "01-journal-no-page-home.png", "只在这页；不会保存到磁盘");
    await backHome(cdp);

    // ② 求助页：HOME_HUB 开着时本来就没有页内回首页，这里一起锁住。
    await clickText(cdp, "我现在很难受");
    await expectPage(cdp, "help-self", "02-help-self-no-page-home.png", "先打这一个");
    await backHome(cdp);

    // ③ 趣味小测试独立页：页头与结果页的回首页都撤掉。
    await clickCard(cdp, "趣味小测试");
    await expectPage(cdp, "quiz", "03-quiz-no-page-home.png", "四个小游戏，没有对错");
    await backHome(cdp);

    // ④ 角色卡：侧栏曾同时出现两个回首页，现在只留 app._nav 那一个。
    await clickCard(cdp, "给心屿一张角色卡");
    await expectPage(cdp, "rolecard", "04-rolecard-single-home.png", "先读这几条");
    await backHome(cdp);

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
