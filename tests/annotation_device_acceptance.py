import sys,time,json
sys.path.insert(0,'tests')
from device import connect,evaluate,protocol

BOOK='/web/reader/33332bf05cbba0333b1efb4'

def event(c,kind,key,code,vk):
    protocol(c,'Input.dispatchKeyEvent',{'type':kind,'key':key,'code':code,'windowsVirtualKeyCode':vk,'nativeVirtualKeyCode':vk})

def press(c,key,code):
    vk={'Insert':45,'Delete':46,'F10':121,'Enter':13,'Escape':27}[key]
    event(c,'keyDown',key,code,vk); event(c,'keyUp',key,code,vk)

def ev(c,expr):
    return evaluate(c,expr)

c=connect()
try:
    ev(c,"location.href="+json.dumps('https://weread.qq.com'+BOOK)+"")
    deadline=time.time()+25
    while time.time()<deadline:
        try:
            if ev(c,"document.querySelectorAll('.wr_underline_wrapper').length>0 && /\\/web\\/reader\\//.test(location.pathname)"): break
        except Exception: pass
        time.sleep(.5)
    time.sleep(1)
    base=ev(c,"(function(){var e=document.querySelector('.readerChapterContent,.preRenderContent');var s=e?getComputedStyle(e):null;return {underlines:document.querySelectorAll('.wr_underline_wrapper').length,layout:e?[s.width,s.padding,s.fontSize,s.lineHeight,s.letterSpacing,s.textAlign]:null,url:location.pathname};})()")
    press(c,'Insert','Insert'); time.sleep(.6)
    selected=ev(c,"({mark:document.querySelectorAll('.wr-hh-annotation').length,data:document.querySelectorAll('[data-wr-hh-annotation]').length,diag:document.getElementById('wr-diag')&&document.getElementById('wr-diag').textContent})")
    assert selected['mark']==1, selected
    assert selected['diag'] and 'annotation' in selected['diag'], selected
    press(c,'Enter','Enter'); time.sleep(1.6)
    opened=ev(c,"({visible:Array.from(document.querySelectorAll('.reader_float_panel_container,[class*=float_panel]')).filter(e=>{var r=e.getBoundingClientRect();return r.width>60&&r.height>60&&getComputedStyle(e).display!=='none'}).map(e=>String(e.className).slice(0,100)),ann:document.querySelectorAll('.wr-hh-annotation').length})")
    assert opened['visible'], opened
    press(c,'Escape','Escape'); time.sleep(.8)
    closed=ev(c,"({visible:Array.from(document.querySelectorAll('.reader_float_panel_container,[class*=float_panel]')).filter(e=>{var r=e.getBoundingClientRect();return r.width>60&&r.height>60&&getComputedStyle(e).display!=='none'}).length,url:location.pathname})")
    assert closed['visible']==0, closed
    assert closed['url'].startswith('/web/reader/'), closed
    after=ev(c,"(function(){var e=document.querySelector('.readerChapterContent,.preRenderContent');var s=e?getComputedStyle(e):null;return e?[s.width,s.padding,s.fontSize,s.lineHeight,s.letterSpacing,s.textAlign]:null;})()")
    print('base',json.dumps(base,ensure_ascii=False))
    print('selected',json.dumps(selected,ensure_ascii=False))
    print('opened',json.dumps(opened,ensure_ascii=False))
    print('closed',json.dumps(closed,ensure_ascii=False))
    print('layoutUnchanged',base['layout']==after)
    assert base['layout']==after, {'base':base,'after':after}
finally:
    c.close()
