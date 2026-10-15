const fs=require("fs");
const r=JSON.parse(fs.readFileSync("/tmp/today.json","utf8"));
const R=n=>Math.round(n*100)/100;
const W=r.filter(x=>x.net>0), L=r.filter(x=>x.net<=0);
const avg=(a,k)=>a.length?a.reduce((s,x)=>s+(x[k]||0),0)/a.length:0;

console.log("### MONEYNESS (abs delta) ###");
const bd={};
r.forEach(x=>{const ad=Math.abs(x.delta);const b=ad>=0.65?"deepITM>=.65":ad>=0.45?"ATM .45-.65":"OTM<.45";bd[b]=bd[b]||{n:0,w:0,net:0};bd[b].n++;bd[b].w+=x.net>0?1:0;bd[b].net+=x.net;});
Object.entries(bd).forEach(([k,v])=>console.log(k.padEnd(14),"n",v.n,"win",v.w,"wr",R(v.w/v.n*100)+"%","net",R(v.net)));

console.log("\n### selectedDelta vs actual delta ###");
console.log("selDelta set",[...new Set(r.map(x=>x.selDelta))],"selIv set",[...new Set(r.map(x=>x.selIv))]);
console.log("actual delta range",R(Math.min(...r.map(x=>Math.abs(x.delta)))),"-",R(Math.max(...r.map(x=>Math.abs(x.delta)))));

console.log("\n### OI & FLOW ###");
console.log("avg oi",R(avg(r,"oi")),"avg optVol",R(avg(r,"optVol")),"avg cpOi",R(avg(r,"cpOi")));
console.log("oiChange set",[...new Set(r.map(x=>x.oiChange))]);
console.log("Wins avg oi",R(avg(W,"oi")),"Loss avg oi",R(avg(L,"oi")));
console.log("Wins avg optVol",R(avg(W,"optVol")),"Loss avg optVol",R(avg(L,"optVol")));

console.log("\n### FEATURE SIGNALS (raw) ###");
console.log("volBurst set",[...new Set(r.map(x=>x.volBurst))]);
console.log("priceVel set",[...new Set(r.map(x=>x.priceVel))]);
console.log("sVolBurst set",[...new Set(r.map(x=>x.sVolBurst))]);

console.log("\n### PCR / IV SKEW / MAXPAIN ###");
console.log("pcr range",Math.min(...r.map(x=>x.pcr)),"-",Math.max(...r.map(x=>x.pcr)),"avg",R(avg(r,"pcr")));
console.log("Wins avg pcr",R(avg(W,"pcr")),"Loss avg pcr",R(avg(L,"pcr")));
console.log("ivSkew range",Math.min(...r.map(x=>x.ivSkew)),"-",Math.max(...r.map(x=>x.ivSkew)),"avg",R(avg(r,"ivSkew")));
console.log("maxPainDist avg",R(avg(r,"maxPainDist")),"Wins",R(avg(W,"maxPainDist")),"Loss",R(avg(L,"maxPainDist")));

const ceP=r.filter(x=>x.side==="CE"), peP=r.filter(x=>x.side==="PE");
console.log("\nCE trades avg pcr",R(avg(ceP,"pcr")),"net",R(ceP.reduce((s,x)=>s+x.net,0)));
console.log("PE trades avg pcr",R(avg(peP,"pcr")),"net",R(peP.reduce((s,x)=>s+x.net,0)));

console.log("\n### PENALTIES ###");
const pen={lunch:0,pe:0,cluster:0,drawdown:0};
r.forEach(x=>{if(x.penalties)for(const k in pen)pen[k]+=x.penalties[k]||0;});
console.log(JSON.stringify(pen),"trades w/ any penalty",r.filter(x=>x.penalties&&Object.values(x.penalties).some(v=>v>0)).length);

console.log("\n### CANDIDATE POOL ###");
console.log("totalCandidates:",r.map(x=>x.totCand).join(","));

console.log("\n### FEATURE CONTRIBUTIONS (summed, wins vs losses) ###");
const fkeys=["price_vel","vol_burst","oi_accel","ba_press","ema_cross","sr","vwap","pcr","maxpain","iv_skew"];
const fc={};fkeys.forEach(k=>fc[k]={w:0,l:0});
r.forEach(x=>{if(x.fc)fkeys.forEach(k=>{if(x.net>0)fc[k].w+=x.fc[k]||0;else fc[k].l+=x.fc[k]||0;});});
fkeys.forEach(k=>console.log(k.padEnd(10),"win",R(fc[k].w),"loss",R(fc[k].l)));

console.log("\n### LATENCY vs OUTCOME buckets ###");
const lb={};
r.forEach(x=>{const s=x.latencyMs/1000;const b=s<10?"a <10s":s<60?"b 10-60s":s<300?"c 1-5m":s<900?"d 5-15m":"e >15m";lb[b]=lb[b]||{n:0,w:0,net:0};lb[b].n++;lb[b].w+=x.net>0?1:0;lb[b].net+=x.net;});
Object.keys(lb).sort().forEach(k=>console.log(k.padEnd(10),"n",lb[k].n,"win",lb[k].w,"net",R(lb[k].net)));

console.log("\n### ENTRY DRIFT: entry vs limitPrice (chasing) ###");
// entrySlip already = entry - limit
console.log("entrySlip set",r.map(x=>x.entrySlip).join(","));
