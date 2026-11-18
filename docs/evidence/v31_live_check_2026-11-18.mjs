import puppeteer from "puppeteer-core";
import fs from "node:fs";

const EDGE = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const URL = "https://xinyu-mindisle.streamlit.app/";
const DIR = process.argv[2] || ".";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const log = (...a) => console.log(...a);

const browser = await puppeteer.launch({
  executablePath: EDGE,
  headless: "new",
  args: ["--no-sandbox", "--disable-dev-shm-usage", "--window-size=1440,1280"],
  defaultViewport: { width: 1440, height: 1280 },
  protocolTimeout: 300000,
});

const page = await browser.newPage();

/** 选真正渲染出应用的 frame：文本最长且含「心屿」 */
async function appFrame(minLen = 200) {
  let best = null, bestLen = 0;
  for (const f of page.frames()) {
    try {
      const t = await f.evaluate(() => document.body ? document.body.innerText : "");
      if (t.includes("心屿") && t.length > bestLen) { best = f; bestLen = t.length; }
    } catch {}
  }
  return bestLen >= minLen ? best : null;
}

await page.goto(URL, { waitUntil: "domcontentloaded", timeout: 60000 });
await sleep(5000);
if (await page.evaluate(() => {
  const b = Array.from(document.querySelectorAll("button, a")).find((e) => /get this app back up/i.test(e.innerText || ""));
  if (b) { b.click(); return true; } return false;
})) { log("woke"); await sleep(10000); }

let frame = null;
const deadline = Date.now() + 180000;
while (Date.now() < deadline && !frame) { frame = await appFrame(300); if (!frame) await sleep(4000); }
if (!frame) { log("NO APP FRAME"); await browser.close(); process.exit(1); }
log("frame:", frame.url());

// 等首页按钮
let labels = [];
for (let i = 0; i < 30; i++) {
  labels = await frame.evaluate(() => Array.from(document.querySelectorAll("button")).map((b) => (b.innerText || "").trim()).filter(Boolean));
  if (labels.includes("进去看看")) break;
  await sleep(3000);
}
log("home buttons:", JSON.stringify(labels));

const count = await frame.evaluate(() => {
  const btns = Array.from(document.querySelectorAll("button")).filter((b) => (b.innerText || "").trim() === "进去看看");
  if (btns.length) { btns[0].click(); return btns.length; }
  return 0;
});
log("enter-chat click:", count);
await sleep(9000);
frame = await appFrame(300) || frame;

const after = await frame.evaluate(() => document.body.innerText);
log("=== CHAT PAGE (head 700) ===");
log(after.slice(0, 700));

let reply = "";
let ok = false;
try {
  let ta = null;
  for (let i = 0; i < 20 && !ta; i++) { ta = await frame.$('textarea[data-testid="stChatInputTextArea"]'); if (!ta) await sleep(3000); }
  log("textarea:", Boolean(ta));
  if (ta) {
    await ta.click();
    await ta.type("今天有点累，想安静一会儿。", { delay: 25 });
    await page.keyboard.press("Enter");
    log("sent");
    const end = Date.now() + 150000;
    while (Date.now() < end) {
      try {
        reply = await frame.evaluate(() =>
          Array.from(document.querySelectorAll('[data-testid="stChatMessage"]')).map((n) => n.innerText).join("\n---\n"));
      } catch {}
      if (reply.length > 30) { ok = true; break; }
      await sleep(4000);
    }
  }
} catch (e) { log("chat error:", e.message); }

const sidebar2 = await frame.evaluate(() => {
  const sb = document.querySelector('[data-testid="stSidebar"]');
  return sb ? sb.innerText : "(none)";
});
const markers = await frame.evaluate(() => {
  const t = document.body.innerText;
  return { demo: t.includes("演示模式"), pending: t.includes("正在输入"), trace: t.includes("本轮编排") };
});

log("=== SIDEBAR ===");
log(sidebar2.slice(0, 1200));
log("=== CHAT ===");
log(reply.slice(0, 1200));
log("markers:", JSON.stringify(markers));

await page.screenshot({ path: `${DIR}\\v31-live-chat-2026-11-18.png` });
fs.writeFileSync(`${DIR}\\v31-live-chat-2026-11-18.txt`,
  `home buttons: ${JSON.stringify(labels)}\nenter-chat clicks: ${count}\nreply captured: ${ok}\n\n=== SIDEBAR ===\n${sidebar2}\n\n=== CHAT ===\n${reply}\n\n=== MARKERS ===\n${JSON.stringify(markers, null, 2)}\n`, "utf8");
await browser.close();
