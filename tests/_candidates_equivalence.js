// Prove the candidates() filter + tab-merge refactor is behavior-identical.
const innerWidth = 640, innerHeight = 480, NAV = 'wr-hh-nav', MENU = 'wr-hh-menu';
const ROWH = 28, window = { scrollY: 0 };

const gcs = (e) => e.style2 || { display:'block', visibility:'visible', opacity:'1' };
function shownSized(e, r){
  const cs = gcs(e);
  if (cs.display === 'none' || cs.visibility === 'hidden') return false;
  if (parseFloat(cs.opacity || '1') < 0.04) return false;
  return true;
}
function shown(e){
  if (!e || !e.isConnected) return false;
  const r = e._rect;
  if (r.width < 18 || r.height < 14) return false;
  return shownSized(e, r);
}
const rc = (e) => e._rect;
function isTextish(e){ return e.tagName === 'INPUT' || e.tagName === 'TEXTAREA' || !!e.isContentEditable; }
function mine(e){ return !!(e.closest && e.closest('#'+NAV+',#'+MENU+',#wr-hh-kbd')); }
function rowOf(r){ return Math.round((r.top + r.height/2 + window.scrollY)/ROWH); }

function mk(tag, cls, rect, opts={}){
  return {
    tagName: tag, className: cls||'', _rect: rect, isConnected: opts.connected !== false,
    style2: opts.style, ours: !!opts.ours,
    closest: (s)=> (opts.ours && s.includes(NAV)) ? {} : null,
    getAttribute: ()=>null, style:{}, matches: ()=>false,
    classList: { contains: (c)=> (cls||'').includes(c), add(){}, remove(){} },
  };
}

// ---- ORIGINAL filter ----
function filterOld(raw, activePanel){
  const list=[];
  for (let i=0;i<raw.length;i++){
    const e=raw[i];
    if (activePanel && !activePanel.contains(e)) continue;
    if (activePanel && e.classList.contains('font-panel-content-fonts-tab')) continue;
    if (mine(e) && !e.matches('#'+NAV+' .wr-hh-tab')) continue;
    if (isTextish(e)) continue;
    if (!shown(e)) continue;
    const r = rc(e);
    if (r.width * r.height > innerWidth * innerHeight * 0.60) continue;
    list.push(e);
  }
  const out=[], selectedSet=new Set(list);
  for (let j=0;j<list.length;j++){
    const el=list[j]; let keep=true;
    for (let p=el.parentElement; p && p !== globalThis.__BODY__; p=p.parentElement){
      if (selectedSet.has(p)){ keep=false; break; }
    }
    if (keep) out.push(el);
  }
  return out;
}
// ---- NEW filter ----
function filterNew(raw, activePanel){
  const list=[];
  for (let i=0;i<raw.length;i++){
    const e=raw[i];
    if (activePanel && !activePanel.contains(e)) continue;
    if (activePanel && e.classList.contains('font-panel-content-fonts-tab')) continue;
    if (mine(e) && !e.matches('#'+NAV+' .wr-hh-tab')) continue;
    if (isTextish(e)) continue;
    if (!e.isConnected) continue;
    const r = rc(e);
    if (r.width < 18 || r.height < 14) continue;
    if (!shownSized(e, r)) continue;
    if (r.width * r.height > innerWidth * innerHeight * 0.60) continue;
    list.push(e);
  }
  const out=[], selectedSet=new Set(list);
  for (let j=0;j<list.length;j++){
    const el=list[j]; let keep=true;
    for (let p=el.parentElement; p && p !== globalThis.__BODY__; p=p.parentElement){
      if (selectedSet.has(p)){ keep=false; break; }
    }
    if (keep) out.push(el);
  }
  return out;
}
// ---- tab merge old vs new ----
function mergeOld(out, tabs){
  const o = out.slice();
  for (let k=0;k<tabs.length;k++) if (shown(tabs[k]) && o.indexOf(tabs[k]) < 0) o.push(tabs[k]);
  return o;
}
function mergeNew(out, tabs){
  const o = out.slice();
  const inOut = new Set(o), tabSet = new Set(tabs);
  for (let k=0;k<tabs.length;k++) if (shown(tabs[k]) && !inOut.has(tabs[k])) { o.push(tabs[k]); inOut.add(tabs[k]); }
  return o;
}
globalThis.__BODY__ = { tagName:'BODY' };

const R = (w,h,top,left)=>({width:w,height:h,top:top,left:left,right:left+w,bottom:top+h});
const cases = [
  ['normal card',        [mk('DIV','shelfBook',R(140,174,10,10))]],
  ['tiny element',       [mk('DIV','shelfBook',R(10,10,10,10))]],
  ['text input',         [mk('INPUT','navBar_input',R(140,174,10,10))]],
  ['hidden display',     [mk('DIV','shelfBook',R(140,174,10,10),{style:{display:'none'}})]],
  ['opacity 0',          [mk('DIV','shelfBook',R(140,174,10,10),{style:{opacity:'0'}})]],
  ['huge overlay',       [mk('DIV','shelfBook',R(640,400,10,10))]],
  ['disconnected',       [mk('DIV','shelfBook',R(140,174,10,10),{connected:false})]],
  ['our own element',    [mk('DIV','shelfBook',R(140,174,10,10),{ours:true})]],
];
let ok=true;
for (const [desc, raw] of cases){
  const a = filterOld(raw,null), b = filterNew(raw,null);
  const same = a.length===b.length && a.every((v,i)=>v===b[i]);
  if(!same) ok=false;
  console.log((same?'ok ':'BAD'), 'filter', desc.padEnd(18), 'old:',a.length,'new:',b.length);
}
// tab merge
const tabs=[ mk('BUTTON','wr-hh-tab',R(60,38,0,0)), mk('BUTTON','wr-hh-tab',R(60,38,0,70)),
             mk('BUTTON','wr-hh-tab',R(10,10,0,140)) ];
const base=[ mk('DIV','shelfBook',R(140,174,10,10)) ];
const mo=mergeOld(base,tabs), mn=mergeNew(base,tabs);
const ms = mo.length===mn.length && mo.every((v,i)=>v===mn[i]);
if(!ms) ok=false;
console.log((ms?'ok ':'BAD'),'merge tabs','old:',mo.length,'new:',mn.length);
// duplicate tab also in base
const base2=[ tabs[0], mk('DIV','shelfBook',R(140,174,10,10)) ];
const mo2=mergeOld(base2,tabs), mn2=mergeNew(base2,tabs);
const ms2 = mo2.length===mn2.length && mo2.every((v,i)=>v===mn2[i]);
if(!ms2) ok=false;
console.log((ms2?'ok ':'BAD'),'merge w/ dup','old:',mo2.length,'new:',mn2.length);
console.log('EQUIVALENCE:', ok?'PASS':'FAIL');
process.exit(ok?0:1);
