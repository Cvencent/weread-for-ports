import sys,json
sys.path.insert(0,'tests')
from device import connect,evaluate
c=connect()
expr="""(function(){
var sels=['.readerCatalog','.font-panel-content','[class*=\"catalog_\"]','[class*=\"float_panel\"]','[class*=\"readerSetting\"]','[class*=\"readerNote\"]','[class*=\"menu_container\"]'];
var out=[];
for(var s of sels){for(var e of document.querySelectorAll(s)){var r=e.getBoundingClientRect(),cs=getComputedStyle(e);if(r.width>60&&r.height>60&&cs.display!=='none'&&cs.visibility!=='hidden'&&parseFloat(cs.opacity||'1')>=.04&&r.left<innerWidth-20&&r.right>20) out.push({sel:s,cls:String(e.className),rect:[r.left,r.top,r.width,r.height],display:cs.display,opacity:cs.opacity,mine:!!e.closest('#wr-hh-nav,#wr-hh-menu,#wr-hh-kbd')});}}
return out;
})()"""
print(json.dumps(evaluate(c,expr),ensure_ascii=False,indent=2))
c.close()
