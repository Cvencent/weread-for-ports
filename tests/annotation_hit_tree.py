import sys,json
sys.path.insert(0,'tests')
from device import connect,protocol
c=connect()
expr="""(function(){
var el=document.querySelector('[data-wr-hh-annotation]'); if(!el) return {none:true};
var r=el.getBoundingClientRect();
var pts=[[(r.left+r.right)/2,(r.top+r.bottom)/2],[r.left+4,(r.top+r.bottom)/2],[r.right-4,(r.top+r.bottom)/2],[(r.left+r.right)/2,r.top+4],[(r.left+r.right)/2,r.bottom-4]];
return {rect:[r.left,r.top,r.right,r.bottom],points:pts.map(function(p){var h=document.elementFromPoint(p[0],p[1]);var chain=[];var x=h;while(x&&chain.length<6){chain.push((x.tagName||'')+'.'+(typeof x.className==='string'?x.className:''));x=x.parentElement}return {p:p,hit:chain[0],tag:h&&h.tagName,inside:!!(h&&(el===h||el.contains(h)||h.contains(el))),chain:chain};})};
})()"""
print(json.dumps(protocol(c,'Runtime.evaluate',{'expression':expr,'returnByValue':True}).get('result',{}).get('result',{}).get('value'),ensure_ascii=False,indent=2))
c.close()
