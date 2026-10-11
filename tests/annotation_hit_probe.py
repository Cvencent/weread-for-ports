import sys,json
sys.path.insert(0,'tests')
from device import connect,protocol
c=connect()
expr="""(function(){
var el=document.querySelector('[data-wr-hh-annotation]'); if(!el) return {none:true};
var r=el.getBoundingClientRect(),pts=[[r.left+r.width/2,r.top+r.height/2],[r.left+4,r.top+r.height/2],[r.left+r.width-4,r.top+r.height/2],[r.left+r.width/2,r.top+4],[r.left+r.width/2,r.top+r.height-4]];
return {rect:[r.left,r.top,r.right,r.bottom],pts:pts.map(function(p){var h=document.elementFromPoint(p[0],p[1]);return {p:p,hit:h&&h.className,tag:h&&h.tagName,inside:!!(h&&(el===h||el.contains(h)||h.contains(el))),chain:h?Array.from((function(){var a=[],x=h;while(x&&a.length<5){a.push((x.tagName||'')+'.'+(typeof x.className==='string'?x.className:''));x=x.parentElement}return a})()):[]};})};
})()"""
print(json.dumps(protocol(c,'Runtime.evaluate',{'expression':expr,'returnByValue':True}).get('result',{}),ensure_ascii=False,indent=2))
c.close()
