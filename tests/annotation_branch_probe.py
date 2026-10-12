import sys, time
sys.path.insert(0,'tests')
from device import connect,evaluate,protocol
c=connect()
def press(key,vk):
    for t in ('keyDown','keyUp'):
        protocol(c,'Input.dispatchKeyEvent',{'type':t,'key':key,'code':key,'windowsVirtualKeyCode':vk,'nativeVirtualKeyCode':vk})
def st():
    return evaluate(c,"({url:location.pathname,mark:document.querySelectorAll('.wr-hh-annotation').length,data:document.querySelectorAll('[data-wr-hh-annotation]').length,branch:document.body.dataset.wrHhAnnotationBranch||null,handled:document.body.dataset.wrHhAnnotationHandled||null,hint:document.getElementById('wr-hh-hint')&&document.getElementById('wr-hh-hint').textContent})")
try:
    evaluate(c,"location.href='https://weread.qq.com/web/reader/33332bf05cbba0333b1efb4';void 0")
    end=time.time()+28
    while time.time()<end:
        try:
            s=st()
            if s['url'].startswith('/web/reader/') and s['mark']==0: break
        except Exception: pass
        time.sleep(.5)
    time.sleep(1)
    print('pre',st())
    press('F8',119); time.sleep(.8)
    print('f8',st())
finally: c.close()
