// Prove move()'s left/right + up/down selection is unchanged after the
// single-rect-read refactor (including tie behaviour of the old band sort).
const window = { scrollY: 0, scrollX: 0 };
function rc(e){ return e._rect; }
function absTop(e){ return rc(e).top + window.scrollY; }
function absLeft(e){ return rc(e).left + window.scrollX; }

function moveOld(c, t, dir){
  const cr = rc(c);
  const ct = absTop(c), cb = ct + cr.height;
  const cl = absLeft(c), ccol = cl + cr.width/2;
  let best = -1, bs = Infinity, i, r;
  if (dir === 'down' || dir === 'up') {
    for (i=0;i<t.length;i++){
      if (t[i]===c) continue;
      r = rc(t[i]); if (r.width<1) continue;
      const top = absTop(t[i]), col = absLeft(t[i]) + r.width/2;
      const d = (dir==='down') ? (top-ct) : (ct-top);
      if (d<=2) continue;
      const sc = d*1000 + Math.abs(col-ccol);
      if (sc<bs){ bs=sc; best=i; }
    }
  } else {
    const band=[];
    for (i=0;i<t.length;i++){
      if (t[i]===c) continue;
      r = rc(t[i]); if (r.width<1) continue;
      const top2=absTop(t[i]), bot2=top2+r.height;
      const ov = Math.min(bot2,cb)-Math.max(top2,ct);
      if (ov < Math.min(r.height,cr.height)*0.4) continue;
      const left2=absLeft(t[i]), col2=left2+r.width/2;
      if (dir==='right' && col2<=ccol+2) continue;
      if (dir==='left'  && col2>=ccol-2) continue;
      band.push({i:i, d:Math.abs(col2-ccol)});
    }
    if (band.length){ band.sort((a,b)=>a.d-b.d); best=band[0].i; }
    else {
      for (i=0;i<t.length;i++){
        if (t[i]===c) continue;
        r = rc(t[i]); if (r.width<1) continue;
        const top3=absTop(t[i]), col3=absLeft(t[i]) + r.width/2;
        const dy = top3-ct;
        if (dir==='right' && dy<=2) continue;
        if (dir==='left'  && dy>=-2) continue;
        const sc2 = Math.abs(dy)*1000 + (dir==='right'?col3:-col3);
        if (sc2<bs){ bs=sc2; best=i; }
      }
    }
  }
  return best;
}

function moveNew(c, t, dir){
  const cr = rc(c);
  const ct = absTop(c), cb = ct + cr.height;
  const cl = absLeft(c), ccol = cl + cr.width/2;
  let best = -1, bs = Infinity, i, r;
  if (dir === 'down' || dir === 'up') {
    for (i=0;i<t.length;i++){
      if (t[i]===c) continue;
      r = rc(t[i]); if (r.width<1) continue;
      const top = r.top + window.scrollY, col = r.left + window.scrollX + r.width/2;
      const d = (dir==='down') ? (top-ct) : (ct-top);
      if (d<=2) continue;
      const sc = d*1000 + Math.abs(col-ccol);
      if (sc<bs){ bs=sc; best=i; }
    }
  } else {
    let bandBest = Infinity;
    for (i=0;i<t.length;i++){
      if (t[i]===c) continue;
      r = rc(t[i]); if (r.width<1) continue;
      const top2 = r.top + window.scrollY, bot2 = top2 + r.height;
      const ov = Math.min(bot2,cb)-Math.max(top2,ct);
      if (ov < Math.min(r.height,cr.height)*0.4) continue;
      const col2 = r.left + window.scrollX + r.width/2;
      if (dir==='right' && col2<=ccol+2) continue;
      if (dir==='left'  && col2>=ccol-2) continue;
      const dist = Math.abs(col2-ccol);
      if (dist<bandBest){ bandBest=dist; best=i; }
    }
    if (bandBest < Infinity) {
    } else {
      best=-1;
      for (i=0;i<t.length;i++){
        if (t[i]===c) continue;
        r = rc(t[i]); if (r.width<1) continue;
        const top3 = r.top + window.scrollY, col3 = r.left + window.scrollX + r.width/2;
        const dy = top3-ct;
        if (dir==='right' && dy<=2) continue;
        if (dir==='left'  && dy>=-2) continue;
        const sc2 = Math.abs(dy)*1000 + (dir==='right'?col3:-col3);
        if (sc2<bs){ bs=sc2; best=i; }
      }
    }
  }
  return best;
}

function grid(rows, cols, w=140, h=174, gap=10, top0=10, left0=10){
  const out=[];
  for(let r=0;r<rows;r++) for(let c=0;c<cols;c++)
    out.push({_rect:{width:w,height:h,top:top0+r*(h+gap),left:left0+c*(w+gap),right:0,bottom:0}});
  return out;
}
let ok=true, checked=0;
for (const [rows,cols] of [[4,4],[5,3],[3,5],[6,2],[2,6],[1,1],[8,4]]){
  const g = grid(rows,cols);
  for (let ci=0; ci<g.length; ci++){
    for (const dir of ['up','down','left','right']){
      const a = moveOld(g[ci], g, dir), b = moveNew(g[ci], g, dir);
      checked++;
      if (a!==b){ ok=false; console.log('BAD', rows+'x'+cols, 'ci='+ci, dir, 'old='+a, 'new='+b); }
    }
  }
}
// Ties: two elements at identical distance to the right.
{
  const c = {_rect:{width:100,height:100,top:0,left:0,right:0,bottom:0}};
  const t = [c, {_rect:{width:100,height:100,top:0,left:200,right:0,bottom:0}},
                {_rect:{width:100,height:100,top:0,left:200,right:0,bottom:0}}];
  for (const dir of ['right','left']){
    const a=moveOld(c,t,dir), b=moveNew(c,t,dir); checked++;
    if(a!==b){ ok=false; console.log('BAD tie', dir, a, b); }
  }
}
// Scroll offset applied.
window.scrollY = 250; window.scrollX = 33;
{
  const g = grid(5,4);
  for (let ci=0;ci<g.length;ci++) for (const dir of ['up','down','left','right']){
    const a=moveOld(g[ci],g,dir), b=moveNew(g[ci],g,dir); checked++;
    if(a!==b){ ok=false; console.log('BAD scrolled', dir, a, b); }
  }
}
console.log('cases checked:', checked);
console.log('EQUIVALENCE:', ok?'PASS':'FAIL');
process.exit(ok?0:1);
