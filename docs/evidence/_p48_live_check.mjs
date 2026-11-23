// 线上核验：无头 Edge + CDP，检查 Streamlit Cloud 是否已跑 main（v3.3）的界面。
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const EDGE = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const PORT = 9228;
const URL_LIVE = "https://xinyu-mindisle.streamlit.app";
const OUT = "docs/evidence/P48-live-2026-11-23";
const W = 1360;
const H = 1020;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

class CDP {
  constructor(ws) {
    this.ws = ws;
    this.id = 0;
    this.pending = new Map();
    ws.addEventListener("message", (e) => {
      const msg = JSON.parse(e.data);
      if (msg.id && this.pending.has(msg.id)) {
        const { resolve, reject } = this.pending.get(msg.id);
        this.pending.delete(msg.id);
        msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result);
      }
    });
  }
  send(method, params = {}) {
    const id = ++this.id;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }
}

async function ev(cdp, expression) {
  const r = await cdp.send("Runtime.evaluate", {
    expression,
    returnByValue: true,
    awaitPromise: true,
  });
  return r.result?.value;
}

async function waitFor(cdp, expr, timeoutMs, label) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    const v = await ev(cdp, expr).catch(() => null);
    if (v) return v;
    await sleep(1500);
  }
  throw new Error(`timeout waiting for ${label}`);
}

async function shot(cdp, name) {
  await ev(
    cdp,
    `[…document.querySelectorAll("*")].forEach(e=>{if(e.scrollTop)e.scrollTop=0});true`,
  );
  await sleep(500);
  const r = await cdp.send("Page.captureScreenshot", { format: "png" });
  const file = path.join(OUT, name);
  fs.writeFileSync(file, Buffer.from(r.data, "base64"));
  console.log("shot", name);
}

async function main() {
  fs.mkdirSync(OUT, { recursive: true });
  const edge = spawn(EDGE, [
    "--headless=new",
    `--remote-debugging-port=${PORT}`,
    `--window-size=${W},${H}`,
    "--user-data-dir=" + path.resolve(OUT, "_edge_profile"),
    "--no-first-run",
    "--disable-gpu",
    "about:blank",
  ]);

  try {
    await waitFor(
      { send: async () => null },
      "(()=>fetch('http://127.0.0.1:" + PORT + "/json/version').then(r=>r.ok).catch(()=>false))()",
      30000,
      "edge port",
    ).catch(async () => {
      for (let i = 0; i < 40; i++) {
        try {
          const r = await fetch(`http://127.0.0.1:${PORT}/json/version`);
          if (r.ok) return;
        } catch {}
        await sleep(500);
      }
      throw new Error("edge did not start");
    });

    const tab = await fetch(`http://127.0.0.1:${PORT}/json/new?about:blank`, {
      method: "PUT",
    }).then((r) => r.json());
    const ws = new WebSocket(tab.webSocketDebuggerUrl);
    await new Promise((res) => ws.addEventListener("open", res));
    const cdp = new CDP(ws);
    await cdp.send("Page.enable");
    await cdp.send("Runtime.enable");
    await cdp.send("Emulation.setDeviceMetricsOverride", {
      width: W,
      height: H,
      deviceScaleFactor: 1,
      mobile: false,
    });
    await cdp.send("Page.navigate", { url: URL_LIVE });
    console.log("navigated");

    // 冷启动时先看有没有唤醒按钮
    const awake = await waitFor(
      cdp,
      `(()=>{const t=document.body.innerText;return (t.includes("今天想怎么待一会儿")?"ready":(t.includes("get this app back up")||t.includes("wake")?"sleep":"wait"))})()`,
      120000,
      "first paint",
    );
    console.log("state", awake);

    if (awake === "sleep") {
      await ev(
        cdp,
        `(()=>{const b=[...document.querySelectorAll("button")].find(x=>/back up|wake/i.test(x.innerText));if(b){b.click();return true}return false})()`,
      );
      await waitFor(
        cdp,
        `document.body.innerText.includes("今天想怎么待一会儿")`,
        180000,
        "app awake",
      );
    }

    await waitFor(cdp, `document.body.innerText.includes("今天想怎么待一会儿")`, 180000, "home");
    await sleep(2500);

    const report = await ev(
      cdp,
      `(()=>{const t=document.body.innerText;const has=s=>t.includes(s);
        return {talk:has("与心屿交流一下"),triage:has("你现在想做哪件事"),g1:has("先说说话"),
          g2:has("自己待一会儿"),g3:has("动动脑子"),g4:has("去咨询"),about:has("关于心屿"),
          randomOld:has("随便来一个"),survey:has("匿名问卷"),len:t.length,
          head:t.slice(0,400)}})()`,
    );
    console.log("HOME", JSON.stringify(report, null, 2));
    await shot(cdp, "01-live-home.png");

    // 索引页
    const clicked = await ev(
      cdp,
      `(()=>{const b=[...document.querySelectorAll("button")].find(x=>x.innerText.trim()==="我遇到一件具体的事");if(b){b.click();return true}return false})()`,
    );
    if (clicked) {
      await waitFor(cdp, `document.body.innerText.includes("我遇到的是")`, 60000, "index");
      await sleep(2000);
      const idx = await ev(
        cdp,
        `(()=>{const t=document.body.innerText;return {head:t.includes("26 个入口"),search:t.includes("搜一个词"),back:[...document.querySelectorAll("button")].some(b=>b.innerText.includes("返回上一级"))}})()`,
      );
      console.log("INDEX", JSON.stringify(idx));
      await shot(cdp, "02-live-index.png");
    }

    // 聊天页
    await ev(
      cdp,
      `(()=>{const b=[...document.querySelectorAll("button")].find(x=>x.innerText.trim()==="与心屿交流一下");if(b){b.click();return true}return false})()`,
    );
    await waitFor(cdp, `document.querySelector("textarea")!==null`, 60000, "chat");
    await sleep(2000);
    const chat = await ev(
      cdp,
      `(()=>{const t=document.body.innerText;return {sideTalk:t.includes("与本轮模式"), mode:t.includes("本轮模式")||t.includes("聊天"), risk:t.includes("当前风险等级"), input:!!document.querySelector("textarea")}})()`,
    );
    console.log("CHAT", JSON.stringify(chat));
    await shot(cdp, "03-live-chat.png");

    ws.close();
  } finally {
    edge.kill();
  }
}

main().catch((e) => {
  console.error("FAIL", e.message);
  process.exitCode = 1;
});
