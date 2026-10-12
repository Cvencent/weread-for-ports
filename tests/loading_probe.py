"""Delay shelf rendering and activate the shell timeout retry by gamepad."""
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
 return ws.call(i,method,params).get('result',{})
def ev(expr):
 return call('Runtime.evaluate',{'expression':expr,'returnByValue':True}).get('result',{}).get('value')
def wait(expr,seconds):
 until=time.monotonic()+seconds
 while time.monotonic()<until:
  result=ev(expr)
  if result: return result
  time.sleep(.3)
 raise AssertionError('Timed out '+expr)
def key(k): subprocess.run(['python3','/storage/roms/ports/browser/vpad.py',k],check=True,stdout=subprocess.DEVNULL)
registration=None
try:
 call('Page.enable')
 source="""(function(){
   window.__heldShelf=true;
   new MutationObserver(function(){
     document.querySelectorAll('.shelfBook,.shelfArchive').forEach(e=>e.remove());
   }).observe(document,{childList:true,subtree:true});
 })()"""
 registration=call('Page.addScriptToEvaluateOnNewDocument',{'source':source})['identifier']
 ev("sessionStorage.setItem('wr-hh-loading',JSON.stringify({href:'/web/shelf',text:'正在加载书架',started:Date.now()}));void 0")
 call('Page.navigate',{'url':'https://weread.qq.com/web/shelf'})
 wait("!!document.querySelector('#wr-hh-loading.wr-hh-load-slow button.wr-hh-focus')",22)
 before=ev("({text:document.querySelector('#wr-hh-loading').innerText,pending:JSON.parse(sessionStorage.getItem('wr-hh-loading')),error:!!document.querySelector('.chapterContentError .retry')})")
 assert not before['error'],before
 assert ev("window.__heldShelf && document.querySelectorAll('.shelfBook,.shelfArchive').length===0")
 subprocess.run('XDG_RUNTIME_DIR=/var/run/0-runtime-dir WAYLAND_DISPLAY=wayland-1 grim /tmp/wr-v9-timeout.png',shell=True,check=True)
 call('Page.removeScriptToEvaluateOnNewDocument',{'identifier':registration})
 registration=None
 key('a')
 wait("!window.__heldShelf && location.pathname==='/web/shelf' && !!document.querySelector('.shelfBook') && !!document.querySelector('#wr-hh-nav') && !document.querySelector('#wr-hh-loading') && sessionStorage.getItem('wr-hh-loading')===null",35)
 after=ev("({busy:document.body.getAttribute('aria-busy'),pending:sessionStorage.getItem('wr-hh-loading'),menu:!!document.querySelector('#wr-hh-menu'),url:location.pathname})")
 assert not after['menu'],after
 assert after['pending'] is None and after['busy'] is None,after
 print(json.dumps({'fixture':'DOM rendering delayed; real shell timer and real gamepad A','before':before,'after':after,'gamepadTimeoutRetry':True},ensure_ascii=False))
finally:
 if registration:
  call('Page.removeScriptToEvaluateOnNewDocument',{'identifier':registration})
  call('Page.navigate',{'url':'https://weread.qq.com/web/shelf'})
 ws.close()
'''
client = connect()
try:
    payload = base64.b64encode(script.encode()).decode()
    result = command(client, f"printf '%s' '{payload}' | base64 -d | python3", timeout=100)
    print(result)
    with client.open_sftp() as sftp:
        sftp.get('/tmp/wr-v9-timeout.png', str(OUT / 'v9-loading-timeout.png'))
    (OUT / 'v9-loading-evidence.json').write_text(result, encoding='utf-8')
finally:
    client.close()
