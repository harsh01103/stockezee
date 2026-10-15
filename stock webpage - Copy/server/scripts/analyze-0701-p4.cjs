const fs=require("fs");
const d=JSON.parse(fs.readFileSync("server/data/ledger.json","utf8"));
const T=d.trades.filter(x=>(x.timestamp||"").startsWith("2026-07-01")).sort((a,b)=>new Date(a.timestamp)-new Date(b.timestamp));
const R=n=>Math.round(n*100)/100;

console.log("### SIGNAL EXPIRY VIOLATIONS (Enter Before vs actual order) ###");
T.forEach(t=>{
 const m=t.metadata;
 const raw=m.rawSignalPayload||"";
 const eb=(raw.match(/Enter Before: (\d{2}:\d{2}:\d{2})/)||[])[1];
 const sigT=new Date(m.signalTimestamp);
 const ordT=new Date(t.timestamp);
 const latMin=R(m.signalToOrderLatencyMs/60000);
 const sigClock=sigT.toTimeString().slice(0,8);
 const ordClock=ordT.toTimeString().slice(0,8);
 if(latMin>2) console.log(t.contractSymbol.padEnd(26),"sig",sigClock,"enterBefore",eb,"ACTUAL order",ordClock,"lat",latMin+"m","net",R(t.netPnl));
});

console.log("\n### DEAD-ON-ARRIVAL LOSERS (MFE<=1: never went green) ###");
T.forEach(t=>{ if(t.netPnl<=0 && t.mfe<=1) console.log(t.contractSymbol.padEnd(26),"MFE",R(t.mfe),"MAE",R(t.mae),"net",R(t.netPnl),"hold",t.holdingDuration+"s","dom",t.metadata.dominantFeature); });

console.log("\n### DEAD-STATS z-score features (normalization dead?) ###");
console.log("oi_zscore_15m all zero, volume_zscore_15m all zero -> 15m rolling normalization not populated");

console.log("\n### PE vs CE with penalty context ###");
const ce=T.filter(t=>t.side==="CE"),pe=T.filter(t=>t.side==="PE");
console.log("CE n",ce.length,"net",R(ce.reduce((s,x)=>s+x.netPnl,0)),"win",ce.filter(x=>x.netPnl>0).length);
console.log("PE n",pe.length,"net",R(pe.reduce((s,x)=>s+x.netPnl,0)),"win",pe.filter(x=>x.netPnl>0).length);
console.log("PE penalty applied on",pe.filter(x=>x.metadata.penalties&&x.metadata.penalties.pe>0).length,"of",pe.length,"PE trades");

console.log("\n### CAPITAL EFFICIENCY ###");
let capSum=0,n=0;T.forEach(t=>{if(t.capitalDeployed){capSum+=t.capitalDeployed;n++;}});
console.log("avg capital deployed",R(capSum/n),"avg riskAmount",R(T.reduce((s,x)=>s+(x.metadata.riskAmount||0),0)/T.length));
console.log("max concurrent positions:",Math.max(...T.map(t=>t.concurrentPositions||1)));

console.log("\n### SPREAD (execution friction) ###");
const spr=T.map(t=>t.metadata.bidAskSpread);
console.log("avg bidAsk",R(spr.reduce((a,b)=>a+b)/spr.length),"max",Math.max(...spr),"min",Math.min(...spr));

console.log("\n### WHAT-IF FILTERS (net impact) ###");
const base=T.reduce((s,x)=>s+x.netPnl,0);
console.log("Baseline net",R(base));
const noOiAccel=T.filter(t=>t.metadata.dominantFeature!=="oi_accel").reduce((s,x)=>s+x.netPnl,0);
console.log("Drop oi_accel-dominant:",R(noOiAccel),"(delta +"+R(noOiAccel-base)+")");
const noStale=T.filter(t=>t.metadata.signalToOrderLatencyMs<=300000).reduce((s,x)=>s+x.netPnl,0);
console.log("Drop latency>5min:",R(noStale),"(delta +"+R(noStale-base)+")");
const noDeepItm=T.filter(t=>{const s=t.metadata.spotPrice;const itm=t.side==="CE"?s-t.strike:t.strike-s;return itm/s*100<=0.6;}).reduce((su,x)=>su+x.netPnl,0);
console.log("Drop deep-ITM(>0.6%):",R(noDeepItm),"(delta +"+R(noDeepItm-base)+")");
const combo=T.filter(t=>t.metadata.dominantFeature!=="oi_accel" && t.metadata.signalToOrderLatencyMs<=300000).reduce((s,x)=>s+x.netPnl,0);
console.log("Drop oi_accel + stale:",R(combo),"(delta +"+R(combo-base)+")");
