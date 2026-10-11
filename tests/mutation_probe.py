"""Count page DOM mutations during a reader open (proxy for shell observer wakeups)."""
import base64, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from device import connect, command

remote = r'''
import sys, json, time, subprocess
sys.path.insert(0, "/storage/roms/ports/browser")
import cdp
ws = cdp.WS(cdp.pick_page_target()["webSocketDebuggerUrl"])
mid = 0
def call(method, params=None):
    global mid
    mid += 1
    ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == mid:
            return msg.get("result", {})
def ev(e):
    return call("Runtime.evaluate", {"expression": e, "returnByValue": True, "awaitPromise": True}).get("result", {}).get("value")

RECORDER = r"""
(function(){
  if (window.top!==window) return;
  var KEY='__wrMut';
  try{ sessionStorage.removeItem(KEY); }catch(e){}
  var total=0, t0=performance.now(), buckets={};
  var obs=new MutationObserver(function(recs){
    total+=recs.length;
    var s=Math.floor((performance.now()-t0)/1000);
    buckets[s]=(buckets[s]||0)+recs.length;
  });
  try{ obs.observe(document, {subtree:true, childList:true, attributes:true, characterData:true}); }catch(e){}
  window.__wrMutDump=function(){ return {total:total, buckets:buckets}; };
})();
"""
call("Page.enable")
ident = call("Page.addScriptToEvaluateOnNewDocument", {"source": RECORDER}).get("identifier")
call("Page.navigate", {"url": "https://weread.qq.com/web/shelf"})
end=time.monotonic()+45
while time.monotonic()<end:
    try:
        if ev("location.pathname==='/web/shelf' && !!document.querySelector('.shelfBook,.shelfArchive')"): break
    except Exception: pass
    time.sleep(0.4)
for _ in range(10):
    h=ev("(function(){var f=document.querySelector('.wr-hh-focus');return f?(f.getAttribute('href')||''):''})()")
    if h and "/web/reader/" in h: break
    subprocess.run(["python3","/storage/roms/ports/browser/vpad.py","down"],check=True,stdout=subprocess.DEVNULL)
    time.sleep(0.5)
time.sleep(1.0)
ev("window.__wrMutDump && (window.__wrMutBase = window.__wrMutDump().total); void 0")
t0=time.monotonic()
subprocess.run(["python3","/storage/roms/ports/browser/vpad.py","a"],check=True,stdout=subprocess.DEVNULL)
end=time.monotonic()+120
while time.monotonic()<end:
    try:
        if ev("document.querySelectorAll('.readerChapterContent canvas,.readerChapterContent_container canvas').length>0"): break
    except Exception: pass
    time.sleep(0.3)
time.sleep(2.0)
dump=ev("window.__wrMutDump ? window.__wrMutDump() : null")
base=ev("window.__wrMutBase")
print(json.dumps({"canvasAfterSeconds":round(time.monotonic()-t0,2) if dump else None,
                  "mutationsSincePress": (dump["total"]-base) if (dump and base is not None) else None,
                  "bucketsPerSecond": dump["buckets"] if dump else None}, ensure_ascii=False))
call("Page.removeScriptToEvaluateOnNewDocument", {"identifier": ident})
try: call("Page.navigate", {"url":"https://weread.qq.com/web/shelf"})
except Exception: pass
ws.close()
'''
client = connect()
try:
    payload = base64.b64encode(remote.encode()).decode()
    print(command(client, "printf '%s' '" + payload + "' | base64 -d | python3", timeout=280))
finally:
    client.close()