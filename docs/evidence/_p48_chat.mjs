import fs from "node:fs";
const PORT=9235, OUT="docs/evidence/P48-live-2026-11-23";
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const { spawn } = await import("node:child_process");
const edge=spawn("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",["--headless=new",`--remote-debugging-port=${PORT}`,"--window-size=1360,1020","--user-data-dir="+process.cwd()+"/"+OUT+"/_edge8","--no-first-run","about:blank"]);
for(let i=0;i<40;i++){try{const r=await fetch(`http://127.0.0.1:${PORT}/json/version`);if(r.ok)break}catch{}await sleep(500)}
const tab=await fetch(`http://127.0.0.1:${PORT}/json/new?about:blank`,{method:"PUT"}).then(r=>r.json());
const ws=new WebSocket(tab.webSocketDebuggerUrl); await new Promise(r=>ws.addEventListener("open",r));
let id=0; const pend=new Map();
ws.addEventListener("message",e=>{const m=JSON.parse(e.data); if(m.id&&pend.has(m.id)){pend.get(m.id)(m);pend.delete(m.id)}});
const send=(method,params={})=>new Promise(res=>{const i=++id;pend.set(i,res);ws.send(JSON.stringify({id:i,method,params}))});
const ev=async e=>{const r=await send("Runtime.evaluate",{expression:e,returnByValue:true,awaitPromise:true});return r.result?.result?.value};
await send("Page.enable"); await send("Runtime.enable");
await send("Emulation.setDeviceMetricsOverride",{width:1360,height:1020,deviceScaleFactor:1,mobile:false});
await send("Page.navigate",{url:"https://xinyu-mindisle.streamlit.app/~/+/"});
for(let i=0;i<20;i++){await sleep(2000);const t=(await ev("document.body.innerText"))||"";if(t.includes("今天想怎么待一会儿"))break}
await sleep(2500);
console.log("click talk:", await ev(`(()=>{const b=[...document.querySelectorAll("button")].find(x=>x.innerText.trim()==="与心屿交流一下");if(b){b.click();return true}return false})()`));
let has=false;
for(let i=0;i<15;i++){await sleep(2000);has=await ev(`!!document.querySelector("textarea")`);if(has)break}
console.log("textarea:", has);
await sleep(2000);
if(!has){console.log("NO TEXTAREA");edge.kill();process.exit(0)}
const text="今天有点累，想安静一会儿。";
await ev(`(()=>{const ta=[...document.querySelectorAll("textarea")].filter(x=>x.getBoundingClientRect().width>0).pop();ta.focus();return true})()`);
await send("Input.insertText",{text});
await sleep(600);
await ev(`(()=>{const b=document.querySelector('[data-testid="stChatInputSubmitButton"]');if(b){b.click();return true}return false})()`);
let replied=false;
for(let i=0;i<25;i++){
  await sleep(2000);
  const t=(await ev("document.body.innerText"))||"";
  const idx=t.indexOf(text);
  if(idx>=0 && t.length>idx+text.length+6){ replied=true; const tail=t.slice(idx).replace(/\n+/g," | ").slice(0,180); console.log("AFTER ::", tail); break }
}
console.log("replied:", replied);
await sleep(1500);
const shot=await send("Page.captureScreenshot",{format:"png"});
fs.writeFileSync(OUT+"/03-live-chat.png",Buffer.from(shot.result.data,"base64"));
edge.kill();
