"""Measure actual browser work, or reproduce a failed chapter request."""
import base64
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from device import command, connect

mode = sys.argv[1]
label = sys.argv[2] if len(sys.argv) > 2 else "before"
script = '''
import sys,time,json
sys.path.insert(0,"/storage/roms/ports/browser")
import cdp
ws=cdp.WS(cdp.pick_page_target()["webSocketDebuggerUrl"])
i=0
def call(method,params={}):
 global i
 i+=1
 return ws.call(i,method,params).get("result",{})
def ev(expr):
 return call("Runtime.evaluate",{"expression":expr,"returnByValue":True}).get("result",{}).get("value")
try:
 if MODE=="perf":
  call("Performance.enable")
  def metrics():
   return {m["name"]:m["value"] for m in call("Performance.getMetrics")["metrics"]}
  a=metrics()
  time.sleep(12)
  b=metrics()
  names=["TaskDuration","ScriptDuration","LayoutDuration","RecalcStyleDuration","LayoutCount","RecalcStyleCount"]
  print(json.dumps({"url":ev("location.pathname"),"seconds":12,"delta":{n:b[n]-a[n] for n in names},"heap":b["JSHeapUsedSize"]}))
 else:
  call("Network.enable")
  call("Network.setBlockedURLs",{"urls":["*weread.qq.com/web/book/chapter/*"]})
  call("Page.reload",{"ignoreCache":True})
  for _ in range(55):
   time.sleep(.5)
   result=ev("Array.from(document.querySelectorAll('div,span,button,a')).filter(e=>!e.children.length&&/重试/.test(e.textContent)).map(e=>({html:e.outerHTML,parent:e.parentElement.outerHTML.slice(0,3600)}))")
   if result: break
  print(json.dumps(result,ensure_ascii=False))
finally:
 if MODE!="perf": call("Network.setBlockedURLs",{"urls":[]})
 ws.close()
'''.replace("MODE", repr(mode))
client = connect()
try:
    payload = base64.b64encode(script.encode()).decode()
    result = command(client, f"printf '%s' '{payload}' | base64 -d | python3")
    print(result)
    output = Path(__file__).resolve().parents[1] / "output/playwright"
    output.mkdir(parents=True, exist_ok=True)
    (output / f"v9-{mode}-{label}.json").write_text(result, encoding="utf-8")
finally:
    client.close()
