import sys,time,json
sys.path.insert(0,'tests')
from device import connect,evaluate,protocol

def press(c,key,vk,code=None):
    code=code or key
    for kind in ('keyDown','keyUp'):
        protocol(c,'Input.dispatchKeyEvent',{'type':kind,'key':key,'code':code,'windowsVirtualKeyCode':vk,'nativeVirtualKeyCode':vk})

def state(c):
    return evaluate(c,"""({
      url:location.pathname,
      underlines:document.querySelectorAll('.wr_underline_wrapper').length,
      visibleUnderlines:Array.from(document.querySelectorAll('.wr_underline_wrapper')).filter(e=>{var r=e.getBoundingClientRect();return r.width>8&&r.height>4}).length,
      mark:document.querySelectorAll('.wr-hh-annotation').length,
      marked:document.querySelectorAll('[data-wr-hh-annotation]').length,
      diag:document.getElementById('wr-diag')&&document.getElementById('wr-diag').textContent,
      panels:document.querySelectorAll('.reader_float_panel_container').length,
      visiblePanels:Array.from(document.querySelectorAll('.reader_float_panel_container')).filter(e=>{var r=e.getBoundingClientRect();return r.width>60&&r.height>60&&getComputedStyle(e).display!=='none'}).length,
      menu:!!document.getElementById('wr-hh-menu')
    })""")

c=connect()
try:
    evaluate(c,"location.href='https://weread.qq.com/web/reader/33332bf05cbba0333b1efb4';void 0")
    deadline=time.time()+30
    while time.time()<deadline:
        try:
            s=state(c)
            if s['url'].startswith('/web/reader/') and s['visibleUnderlines']>0: break
        except Exception: pass
        time.sleep(.5)
    time.sleep(1)
    print('reader',json.dumps(state(c),ensure_ascii=False))
    press(c,'F8',119); time.sleep(.7)
    print('f8',json.dumps(state(c),ensure_ascii=False))
    press(c,'Enter',13); time.sleep(2)
    print('a',json.dumps(state(c),ensure_ascii=False))
    press(c,'Escape',27); time.sleep(1)
    print('b',json.dumps(state(c),ensure_ascii=False))
finally:
    c.close()
