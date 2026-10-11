import sys,json
sys.path.insert(0,'tests')
from device import connect,evaluate
c=connect()
expr="""(function(){
var e=document.querySelector('.wr_underline_wrapper'),r=e&&e.getBoundingClientRect(),s=e&&getComputedStyle(e);var nav=document.getElementById('wr-hh-nav'),nr=nav&&nav.getBoundingClientRect();
return {path:location.pathname,count:document.querySelectorAll('.wr_underline_wrapper').length,rect:e?[r.left,r.top,r.right,r.bottom,r.width,r.height]:null,display:s&&s.display,visibility:s&&s.visibility,opacity:s&&s.opacity,connected:e&&e.isConnected,nav:nav?[nr.top,nr.bottom,nr.width,nr.height]:null,inner:[innerWidth,innerHeight],parent:e?[e.parentElement.className,e.parentElement.tagName]:null,outer:e?e.outerHTML.slice(0,500):null};
})()"""
print(json.dumps(evaluate(c,expr),ensure_ascii=False,indent=2))
c.close()
