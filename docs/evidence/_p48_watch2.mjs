import fs from "node:fs";
const PORT=9231, OUT="docs/evidence/P48-live-2026-11-23";
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const { spawn } = await import("node:child_process");
const edge=spawn("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",["--headless=new",`--remote-debugging-port=${PORT}`,"--window-size=1360,1020","--user-data-dir="+process.cwd()+"/"+OUT+"/_edge4","--no-first-run","about:blank"]);
for(let i=0;i<40;i++){try{const r=await fetch(`http://127.0.0.1:${PORT}/json/version`);if(r.ok)break}catch{}await sleep(500)}
const tab=await fetch(`http://127.0.0.1:${PORT}/json/new?about:blank`,{method:"PUT"}).then(r=>r.json());
const ws=new WebSocket(tab.webSocketDebuggerUrl); await new Promise(r=>ws.addEventListener("open",r));
let id=0; const pend=new Map();
ws.addEventListener("message",e=>{const m=JSON.parse(e.data); if(m.id&&pend.has(m.id)){pend.get(m.id)(m);pend.delete(m.id)}});
const send=(method,params={})=>new Promise(res=>{const i=++id;pend.set(i,res);ws.send(JSON.stringify({id:i,method,params}))});
const ev=async e=>{const r=await send("Runtime.evaluate",{expression:e,returnByValue:true,awaitPromise:true});return r.result?.result?.value};
await send("Page.enable"); await send("Runtime.enable");
await send("Emulation.setDeviceMetricsOverride",{width:1360,height:1020,deviceScaleFactor:1,mobile:false});
await send("Page.navigate",{url:"https://xinyu-mindisle.streamlit.app"});
const T=`(()=>{const el=document.querySelector('[data-testid="stAppViewContainer"]')||document.querySelector('section.main');return el?el.innerText:''})()`;
for(let i=0;i<20;i++){
  await sleep(6000);
  const t=await ev(T)||"";
  console.log(`[${(i+1)*6}s] len=${t.length} :: ${t.replace(/\n+/g," | ").slice(0,240)}`);
  if(t.includes("今天想怎么待一会儿")){console.log("HOME OK");break}
  if(t.includes("ImportError")){console.log("IMPORT ERROR");break}
}
const shot=await send("Page.captureScreenshot",{format:"png"});
fs.writeFileSync(OUT+"/01-live-home.png",Buffer.from(shot.result.data,"base64"));
edge.kill();
