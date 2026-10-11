import sys,json
sys.path.insert(0,'tests')
from device import connect, evaluate
c=connect()
try:
    expr = "Array.from(document.querySelectorAll('.readerCatalog,.font-panel-content,[class*=catalog_],[class*=float_panel],[class*=readerSetting],[class*=readerNote],[class*=menu_container]')).map(e=>{var r=e.getBoundingClientRect(),s=getComputedStyle(e);return {cls:String(e.className),rect:[r.left,r.top,r.width,r.height],display:s.display,visibility:s.visibility,opacity:s.opacity,pe:s.pointerEvents,connected:e.isConnected}})"
    print(json.dumps(evaluate(c, expr), ensure_ascii=False, indent=2))
finally:
    c.close()