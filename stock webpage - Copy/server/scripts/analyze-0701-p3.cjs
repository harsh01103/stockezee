const fs=require("fs");
const d=JSON.parse(fs.readFileSync("server/data/ledger.json","utf8"));
const T=d.trades.filter(x=>(x.timestamp||"").startsWith("2026-07-01")).sort((a,b)=>new Date(a.timestamp)-new Date(b.timestamp));
const r=JSON.parse(fs.readFileSync("/tmp/today.json","utf8"));
const R=n=>Math.round(n*100)/100;

console.log("### OI-ACCEL PIPELINE CHECK (are flow features dead?) ###");
const flowKeys=["oi","delta_oi","cum_delta_oi","oi_velocity","oi_acceleration","oi_accel","oi_flow_score","oi_zscore_15m","signed_oi","volume_zscore_15m","delta_volume","signed_volume"];
let allZero={};flowKeys.forEach(k=>allZero[k]=0);
T.forEach(t=>{const f=t.metadata.features||{};flowKeys.forEach(k=>{if((f[k]||0)!==0)allZero[k]++;});});
flowKeys.forEach(k=>console.log(k.padEnd(18),"nonzero in",allZero[k],"/24 trades"));

console.log("\n### oi_accel-DOMINANT trades: what actually drove them ###");
T.filter(t=>t.metadata.dominantFeature==="oi_accel").forEach(t=>{
 const fc=t.metadata.featureContributions||{};const f=t.metadata.features||{};
 console.log(t.contractSymbol,"net",R(t.netPnl),"| raw oi_accel",f.oi_accel,"| contrib oi_accel",R(fc.oi_accel),"| next:ba_press",R(fc.ba_press),"vol_burst",R(fc.vol_burst));
});

console.log("\n### TRUE MONEYNESS vs SPOT ###");
const mn={};
T.forEach(t=>{const spot=t.metadata.spotPrice;const k=t.strike;const side=t.side;
 // ITM if CE strike<spot, PE strike>spot
 let itm = side==="CE"? spot-k : k-spot; // >0 = ITM points
 const pct=itm/spot*100;
 const b=pct>0.6?"ITM>0.6%":pct>-0.2?"ATM +-":pct>-1?"OTM 0.2-1%":"far OTM>1%";
 mn[b]=mn[b]||{n:0,w:0,net:0};mn[b].n++;mn[b].w+=t.netPnl>0?1:0;mn[b].net+=t.netPnl;
});
Object.entries(mn).forEach(([k,v])=>console.log(k.padEnd(12),"n",v.n,"win",v.w,"net",R(v.net)));

console.log("\n### MFE GIVEBACK / TARGET EFFICIENCY (winners) ###");
r.filter(x=>x.net>0).forEach(x=>{
 const captured=x.exit-x.entry; // for the option premium (both CE/PE premium rises when right)
 const giveback=x.mfe-Math.abs(captured);
 console.log(x.sym.padEnd(26),"entry",x.entry,"exit",x.exit,"MFE",x.mfe,"captured",R(Math.abs(captured)),"giveback",R(giveback));
});

console.log("\n### STALE SIGNAL CASES (latency>5min) ###");
T.filter(t=>t.metadata.signalToOrderLatencyMs>300000).sort((a,b)=>b.metadata.signalToOrderLatencyMs-a.metadata.signalToOrderLatencyMs).forEach(t=>{
 console.log(t.contractSymbol.padEnd(26),"latency",R(t.metadata.signalToOrderLatencyMs/60000)+"min","net",R(t.netPnl),"exit",t.exitReason,"limit",t.metadata.limitPrice,"entry",t.entryPrice);
});

console.log("\n### R-MULTIPLE HISTOGRAM ###");
const rh={};
r.forEach(x=>{const b=x.R<=-1?"<=-1 (full SL)":x.R<0?"-1..0":x.R<1.5?"0..1.5":x.R<2?"1.5..2":">=2";rh[b]=(rh[b]||0)+1;});
Object.entries(rh).forEach(([k,v])=>console.log(k.padEnd(16),v));

console.log("\n### EXIT REASON ###");
const er={};r.forEach(x=>{er[x.exitReason]=(er[x.exitReason]||0)+1;});
console.log(JSON.stringify(er));
console.log("Note target2 hits:",T.filter(t=>t.exitPrice>=t.metadata.target2).length,"| trailing/time-stops:",T.filter(t=>!/Target|Stop/.test(t.exitReason||"")).length);

console.log("\n### THETA BLEED vs HOLD (was decay a factor?) ###");
r.forEach(x=>{});
const wLong=r.filter(x=>x.holdSec>600);
console.log("trades held >10min:",wLong.length,"avg net",R(wLong.reduce((s,x)=>s+x.net,0)/(wLong.length||1)));
console.log("avg theta/min approx (theta is per day):", R(-11.52/375),"pts/min -> over 11min hold ~", R(-11.52/375*11),"pts premium decay");

console.log("\n### CONSECUTIVE LOSS STREAKS ###");
let streak=0,maxStreak=0,worstRun=0,run=0;
r.forEach(x=>{if(x.net<=0){streak++;run+=x.net;maxStreak=Math.max(maxStreak,streak);worstRun=Math.min(worstRun,run);}else{streak=0;run=0;}});
console.log("max consecutive losses",maxStreak,"worst cumulative run",R(worstRun));
