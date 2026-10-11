import sys,time,json
sys.path.insert(0,'tests')
from device import connect,evaluate,protocol
c=connect()
def press(key,vk):
    for t in ('keyDown','keyUp'):
        protocol(c,'Input.dispatchKeyEvent',{'type':t,'key':key,'code':key,'windowsVirtualKeyCode':vk,'nativeVirtualKeyCode':vk})
def q(expr): return evaluate(c,expr)
try:
    print('start',q("location.pathname"))
    end=time.time()+35; last=None
    while time.time()<end:
        try:
            last=q("({p:location.pathname,n:document.querySelectorAll('.wr_underline_wrapper').length,v:Array.from(document.querySelectorAll('.wr_underline_wrapper')).filter(function(e){return e.getBoundingClientRect().width>8&&e.getBoundingClientRect().height>4}).length,diag:document.getElementById('wr-diag')&&document.getElementById('wr-diag').textContent})")
            if last['p'].startswith('/web/reader/') and last['v']>0: break
        except Exception as e: last=str(e)
        time.sleep(.5)
    print('ready',last)
    time.sleep(2)
    press('F8',119); time.sleep(1)
    print('after',q("({mark:document.querySelectorAll('.wr-hh-annotation').length,data:document.querySelectorAll('[data-wr-hh-annotation]').length,diag:document.getElementById('wr-diag')&&document.getElementById('wr-diag').textContent,cls:Array.from(document.querySelectorAll('.wr_underline_wrapper')).map(function(e){return e.className})})"))
finally:c.close()
