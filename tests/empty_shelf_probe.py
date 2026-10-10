"""Exercise an empty shelf without changing the account's stored books."""
import base64
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from device import command, connect
from e2e import OUT

script = r'''
import sys,json,time,subprocess
sys.path.insert(0,'/storage/roms/ports/browser')
import cdp
ws=cdp.WS(cdp.pick_page_target()['webSocketDebuggerUrl'])
i=0
def call(method,params={}):
 global i
 i+=1
 response=ws.call(i,method,params)
 if 'error' in response: raise RuntimeError(response['error'])
 return response.get('result',{})
def ev(expr):
 return call('Runtime.evaluate',{'expression':expr,'returnByValue':True}).get('result',{}).get('value')
def wait(expr):
 until=time.monotonic()+35
 while time.monotonic()<until:
  if ev(expr): return
  time.sleep(.3)
 raise AssertionError('Timed out '+expr)
registration=None
try:
 call('Page.enable')
 source="""(function(){
   window.__emptyFixture='registered';
   new MutationObserver(function(){
     var container=document.querySelector('.shelf_container');
     if(!container) return;
     container.querySelectorAll('.shelfBook,.shelfArchive').forEach(e=>e.remove());
     if(!container.querySelector('.shelf_empty')){
       var empty=document.createElement('div');empty.className='shelf_empty';
       empty.textContent='书架暂无书籍';container.appendChild(empty);
     }
   }).observe(document,{childList:true,subtree:true});
 })()"""
 registration=call('Page.addScriptToEvaluateOnNewDocument',{'source':source})['identifier']
 ev("sessionStorage.setItem('wr-hh-loading',JSON.stringify({href:'/web/shelf',text:'正在加载书架',started:Date.now()}));window.__emptyOldDocument=true;void 0")
 call('Page.navigate',{'url':'https://weread.qq.com/web/shelf'})
 try:
  wait("!window.__emptyOldDocument && !!document.querySelector('.shelf_empty') && !!document.querySelector('#wr-hh-nav') && !document.querySelector('#wr-hh-loading')")
 except AssertionError:
  print(json.dumps(ev("({url:location.pathname,fixture:window.__emptyFixture,container:!!document.querySelector('.shelf_container'),empty:document.querySelector('.shelf_empty')?.outerHTML,books:document.querySelectorAll('.shelfBook').length,load:document.querySelector('#wr-hh-loading')?.innerText})"),ensure_ascii=False),file=sys.stderr)
  raise
 state=ev("({books:document.querySelectorAll('.shelfBook,.shelfArchive').length,pending:sessionStorage.getItem('wr-hh-loading'),busy:document.body.getAttribute('aria-busy'),text:document.querySelector('.shelf_empty').innerText})")
 assert state['books']==0 and state['pending'] is None and state['busy'] is None,state
 subprocess.run('XDG_RUNTIME_DIR=/var/run/0-runtime-dir WAYLAND_DISPLAY=wayland-1 grim /tmp/wr-v9-empty.png',shell=True,check=True)
 print(json.dumps({'fixture':'DOM-only empty shelf; account books unchanged',**state},ensure_ascii=False))
finally:
 if registration: call('Page.removeScriptToEvaluateOnNewDocument',{'identifier':registration})
 ev('window.__emptyOldDocument=true;void 0')
 call('Page.navigate',{'url':'https://weread.qq.com/web/shelf'})
 wait("!window.__emptyOldDocument && !!document.querySelector('.shelfBook')")
 ws.close()
'''
client = connect()
try:
    payload = base64.b64encode(script.encode()).decode()
    result = command(client, f"printf '%s' '{payload}' | base64 -d | python3", timeout=100)
    (OUT / "v9-empty-shelf-evidence.json").write_text(result, encoding="utf-8")
    with client.open_sftp() as sftp:
        sftp.get("/tmp/wr-v9-empty.png", str(OUT / "v9-empty-shelf.png"))
    print("PASS empty shelf settles loading without stored-book changes")
finally:
    client.close()
