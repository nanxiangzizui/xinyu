import fs from "node:fs";
const PORT=9234, OUT="docs/evidence/P48-live-2026-11-23";
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const { spawn } = await import("node:child_process");
const edge=spawn("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",["--headless=new",`--remote-debugging-port=${PORT}`,"--window-size=1360,1020","--user-data-dir="+process.cwd()+"/"+OUT+"/_edge7","--no-first-run","about:blank"]);
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
let ok=false;
for(let i=0;i<18;i++){
  await sleep(15000);
  const t=(await ev("document.body.innerText"))||"";
  const line=t.replace(/\n+/g," | ").slice(0,160);
  console.log(`[${(i+1)*15}s] len=${t.length} :: ${line}`);
  if(t.includes("今天想怎么待一会儿")){ok=true;break}
}
if(ok){
  await sleep(3000);
  const rep=await ev(`(()=>{const t=document.body.innerText;const h=s=>t.includes(s);return {home:h("今天想怎么待一会儿"),triage:h("你现在想做哪件事"),talk:h("与心屿交流一下"),g1:h("先说说话"),g2:h("自己待一会儿"),g3:h("动动脑子"),g4:h("去咨询"),about:h("关于心屿"),survey:h("匿名问卷"),rand:h("随便来一个"),res12356:h("12356"),res110:h("110")}})()`);
  console.log("HOME", JSON.stringify(rep));
  const shot=await send("Page.captureScreenshot",{format:"png"});
  fs.writeFileSync(OUT+"/01-live-home.png",Buffer.from(shot.result.data,"base64"));
  // 索引页
  const clicked=await ev(`(()=>{const b=[...document.querySelectorAll("button")].find(x=>x.innerText.trim()==="我遇到一件具体的事");if(b){b.click();return true}return false})()`);
  if(clicked){
    for(let i=0;i<10;i++){await sleep(3000);const t=(await ev("document.body.innerText"))||"";if(t.includes("我遇到的是"))break}
    const idx=await ev(`(()=>{const t=document.body.innerText;return {title:t.includes("我遇到的是"),head:t.includes("26 个入口"),search:t.includes("搜一个词"),back:[...document.querySelectorAll("button")].some(b=>b.innerText.includes("返回上一级"))}})()`);
    console.log("INDEX", JSON.stringify(idx));
    const s2=await send("Page.captureScreenshot",{format:"png"});
    fs.writeFileSync(OUT+"/02-live-index.png",Buffer.from(s2.result.data,"base64"));
  }
} else {
  const shot=await send("Page.captureScreenshot",{format:"png"});
  fs.writeFileSync(OUT+"/01-live-still-broken.png",Buffer.from(shot.result.data,"base64"));
  console.log("STILL BROKEN");
}
edge.kill();
