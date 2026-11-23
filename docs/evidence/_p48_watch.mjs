import fs from "node:fs";
const PORT=9230, OUT="docs/evidence/P48-live-2026-11-23";
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const { spawn } = await import("node:child_process");
const edge=spawn("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",["--headless=new",`--remote-debugging-port=${PORT}`,"--window-size=1360,1020","--user-data-dir="+process.cwd()+"/"+OUT+"/_edge3","--no-first-run","about:blank"]);
for(let i=0;i<40;i++){try{const r=await fetch(`http://127.0.0.1:${PORT}/json/version`);if(r.ok)break}catch{}await sleep(500)}
const tab=await fetch(`http://127.0.0.1:${PORT}/json/new?about:blank`,{method:"PUT"}).then(r=>r.json());
const ws=new WebSocket(tab.webSocketDebuggerUrl); await new Promise(r=>ws.addEventListener("open",r));
let id=0; const pend=new Map();
ws.addEventListener("message",e=>{const m=JSON.parse(e.data); if(m.id&&pend.has(m.id)){pend.get(m.id)(m);pend.delete(m.id)}});
const send=(method,params={})=>new Promise(res=>{const i=++id;pend.set(i,res);ws.send(JSON.stringify({id:i,method,params}))});
await send("Page.enable"); await send("Runtime.enable");
await send("Emulation.setDeviceMetricsOverride",{width:1360,height:1020,deviceScaleFactor:1,mobile:false});
await send("Page.navigate",{url:"https://xinyu-mindisle.streamlit.app"});
for (let i=0;i<24;i++){
  await sleep(5000);
  const r=await send("Runtime.evaluate",{expression:"document.documentElement.textContent.replace(/\\s+/g,' ').slice(0,900)",returnByValue:true});
  const txt=r.result?.result?.value||"";
  console.log(`[${(i+1)*5}s]`, txt.slice(0,300));
  if(txt.includes("今天想怎么待一会儿")){ console.log("HOME OK"); break; }
  if(txt.includes("ImportError")||txt.includes("Traceback")){ console.log("ERR", txt); break; }
}
edge.kill();
