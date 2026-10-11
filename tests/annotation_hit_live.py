import sys,time,json
sys.path.insert(0,'tests')
from device import connect,evaluate,protocol
c=connect()
def press(key,vk):
    for t in ('keyDown','keyUp'):
        protocol(c,'Input.dispatchKeyEvent',{'type':t,'key':key,'code':key,'windowsVirtualKeyCode':vk,'nativeVirtualKeyCode':vk})
try:
    evaluate(c,"location.href='https://weread.qq.com/web/reader/33332bf05cbba0333b1efb4';void 0")
    end=time.time()+28
    while time.time()<end:
        try:
            if evaluate(c,"location.pathname.indexOf('/web/reader/')===0&&document.querySelectorAll('.wr_underline_wrapper').length>0"): break
        except Exception: pass
        time.sleep(.5)
    time.sleep(1)
    press('F8',119); time.sleep(.8)
    expr="""(function(){
    var el=document.querySelector('[data-wr-hh-annotation]'); if(!el) return {none:true};
    var r=el.getBoundingClientRect(),pts=[[r.left+r.width/2,r.top+r.height/2],[r.left+4,r.top+r.height/2],[r.left+r.width-4,r.top+r.height/2],[r.left+r.width/2,r.top+4],[r.left+r.width/2,r.top+r.height-4]];
    return {mark:document.querySelectorAll('.wr-hh-annotation').length,rect:[r.left,r.top,r.right,r.bottom],pts:pts.map(function(p){var h=document.elementFromPoint(p[0],p[1]);return {p:p,hit:h&&h.className,tag:h&&h.tagName,inside:!!(h&&(el===h||el.contains(h)||h.contains(el)))};})};
    })()"""
    print(json.dumps(evaluate(c,expr),ensure_ascii=False,indent=2))
finally:c.close()
