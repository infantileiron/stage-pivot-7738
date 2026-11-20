export const money=c=>(c/100).toLocaleString('zh-CN',{minimumFractionDigits:2,maximumFractionDigits:2});export const pct=v=>v===null?'未定义':(v*100).toFixed(1)+'%';
export const rate=m=>m===null||m===undefined?'—':(m/1000000).toLocaleString('zh-CN',{minimumFractionDigits:4,maximumFractionDigits:6});
export const fxmoney=(cur,c)=>c===null||c===undefined?'—':cur+' '+money(c);
export const signed=c=>(c>0?'+':'')+money(c);
