import sys,time,json
sys.path.insert(0,"tests")
from device import connect, evaluate
c=connect()
try:
    expr = "({url:location.pathname,isReaderPath:/\\/web\\/reader\\//.test(location.pathname),ann:document.querySelectorAll('wr_underline_wrapper').length})"
    print(evaluate(c,expr))
    print(evaluate(c,"({underlines:document.querySelectorAll('.wr_underline_wrapper').length,vis:Array.from(document.querySelectorAll('.wr_underline_wrapper')).map(e=>{var r=e.getBoundingClientRect();return [r.left,r.top,r.width,r.height,getComputedStyle(e).display,getComputedStyle(e).visibility,getComputedStyle(e).opacity]}),panels:document.querySelectorAll('.readerCatalog,.font-panel-content').length,diag:document.getElementById('wr-diag')?document.getElementById('wr-diag').textContent:null,perf:document.body.className})"))
finally:
    c.close()
