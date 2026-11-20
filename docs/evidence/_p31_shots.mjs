// 临时脚本：用 Edge headless + CDP 截取 P26–P30 页面截图（不进入仓库运行时）。
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const EDGE = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const BASE = "http://127.0.0.1:8517";
const OUT = path.resolve("docs/evidence/shots-P31");
const PORT = 9222;
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
    `(()=>{const b=[...document.querySelectorAll("button")].find(x=>x.innerText.trim()===${JSON.stringify(text)});
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

async function home(cdp) {
  await cdp.send("Page.navigate", { url: BASE + "/?u=shots" });
  if (!(await waitText(cdp, "今天想怎么待一会儿？"))) throw new Error("home not loaded");
  await sleep(900);
}

async function main() {
  const profile = path.resolve("docs/evidence/_p31_edge_profile");
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

    await home(cdp);
    await shot(cdp, "01-home-triage.png");

    await clickText(cdp, "我只是逛逛");
    await waitText(cdp, "展开四个入口");
    await sleep(600);
    await shot(cdp, "02-home-collapsed.png");

    await home(cdp);
    await clickCard(cdp, "跟辅导员 / 老师说");
    await waitText(cdp, "三档");
    await sleep(600);
    await shot(cdp, "10-help-teacher.png");

    await home(cdp);
    await clickCard(cdp, "请假 / 缓考 / 休学");
    await waitText(cdp, "找谁办");
    await sleep(600);
    await shot(cdp, "11-help-leave.png");

    await home(cdp);
    await clickCard(cdp, "陪别人去心理中心 / 医院");
    await waitText(cdp, "不是负责人");
    await sleep(600);
    await shot(cdp, "12-help-accompany.png");

    await home(cdp);
    await clickText(cdp, "我现在很难受");
    await waitText(cdp, "先打这一个");
    await sleep(600);
    await shot(cdp, "03-help-self.png");

    await home(cdp);
    await clickText(cdp, "我朋友出事了");
    await waitText(cdp, "我不会到处说");
    await sleep(600);
    await shot(cdp, "04-help-friend.png");

    await home(cdp);
    await clickCard(cdp, "它是什么、记了什么");
    await waitText(cdp, "能做什么");
    await sleep(700);
    await shot(cdp, "05-about.png");
    await ev(cdp, `(()=>{const m=[...document.querySelectorAll('[data-testid="stMultiSelect"]')][0];
      if(m) m.scrollIntoView({block:"center"}); else window.scrollTo(0, 900); return true;})()`);
    await sleep(700);
    await shot(cdp, "06-about-data.png");

    await home(cdp);
    await clickCard(cdp, "去咨询前，可以准备什么");
    await waitText(cdp, "不知道怎么开口");
    await sleep(600);
    await shot(cdp, "08-help-before.png");

    await home(cdp);
    await clickCard(cdp, "咨询后这一周");
    await waitText(cdp, "有点空");
    await sleep(600);
    await shot(cdp, "09-help-after.png");

    await home(cdp);
    await clickCard(cdp, "写下来");
    await waitText(cdp, "现在最占心思的一件事");
    await sleep(800);
    await ev(cdp, `(()=>{const ta=document.querySelector("textarea"); if(!ta) return false; ta.focus(); return true;})()`);
    await cdp.send("Input.insertText", { text: "今天有点乱，先写一句：晚上没吃，也不太想说话。" });
    await cdp.send("Input.dispatchKeyEvent", {
      type: "keyDown", modifiers: 2, key: "Enter", code: "Enter",
      windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13,
    });
    await cdp.send("Input.dispatchKeyEvent", {
      type: "keyUp", modifiers: 2, key: "Enter", code: "Enter",
      windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13,
    });
    if (!(await waitText(cdp, "写下来了", 15000))) {
      await ev(cdp, `(()=>{const ta=document.querySelector("textarea"); if(ta) ta.blur(); return true;})()`);
      await waitText(cdp, "写下来了", 10000);
    }
    await sleep(600);
    await shot(cdp, "07-journal-ack.png");

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
