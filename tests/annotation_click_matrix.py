import sys,time,json
sys.path.insert(0,'tests')
from device import connect,evaluate,protocol

BOOK='https://weread.qq.com/web/reader/33332bf05cbba0333b1efb4'

def press(c,key,vk):
    for t in ('keyDown','keyUp'):
        protocol(c,'Input.dispatchKeyEvent',{'type':t,'key':key,'code':key,'windowsVirtualKeyCode':vk,'nativeVirtualKeyCode':vk})

def click(c,x,y):
    for t in ('mousePressed','mouseReleased'):
        protocol(c,'Input.dispatchMouseEvent',{'type':t,'x':x,'y':y,'button':'left','clickCount':1})
    time.sleep(1.5)

def state(c):
    return evaluate(c,"""({url:location.pathname, mark:document.querySelectorAll('.wr-hh-annotation').length, data:document.querySelectorAll('[data-wr-hh-annotation]').length, diag:document.getElementById('wr-diag')&&document.getElementById('wr-diag').textContent, visiblePanels:Array.from(document.querySelectorAll('.reader_float_panel_container')).filter(e=>{var r=e.getBoundingClientRect();return r.width>60&&r.height>60&&getComputedStyle(e).display!=='none'}).map(e=>String(e.className).slice(0,120)), top:document.elementFromPoint(innerWidth/2,innerHeight/2)&&document.elementFromPoint(innerWidth/2,innerHeight/2).className})""")

c=connect()
try:
    evaluate(c,"location.href="+json.dumps(BOOK)+";void 0")
    deadline=time.time()+35
    while time.time()<deadline:
        try:
            s=state(c)
            if s['url'].startswith('/web/reader/') and s['mark']==0:
                u=evaluate(c,"document.querySelectorAll('.wr_underline_wrapper').length")
                if u: break
        except Exception: pass
        time.sleep(.5)
    time.sleep(2)
    press(c,'F8',119); time.sleep(1)
    print('selected',json.dumps(state(c),ensure_ascii=False))
    info=evaluate(c,"""(function(){
      var el=document.querySelector('[data-wr-hh-annotation]'); if(!el) return {none:true};
      var r=el.getBoundingClientRect();
      var xs=[(r.left+r.right)/2,r.left+8,r.right-8,(r.left+r.right)/2,(r.left+r.right)/2];
      var ys=[(r.top+r.bottom)/2,(r.top+r.bottom)/2,(r.top+r.bottom)/2,r.top+8,r.bottom-8];
      return {rect:[r.left,r.top,r.right,r.bottom,r.width,r.height],outer:el.outerHTML.slice(0,1000),parent:[el.parentElement.tagName,String(el.parentElement.className),el.parentElement.getAttribute('data-wr-hh-annotation')],children:Array.from(el.children).map(function(x){return [x.tagName,String(x.className),x.getAttribute('data-wr-hh-annotation'),getComputedStyle(x).pointerEvents]}),points:xs.map(function(x,i){var p=[x,ys[i]],hit=document.elementFromPoint(x,ys[i]),chain=[];var z=hit;while(z&&chain.length<8){chain.push((z.tagName||'')+'.'+(typeof z.className==='string'?z.className:''));z=z.parentElement}return {p:p,hit:chain[0],inside:!!(hit&&(el===hit||el.contains(hit)||hit.contains(el))),chain:chain};})};
    })()""")
    print('hit',json.dumps(info,ensure_ascii=False))
    if info and not info.get('none'):
        x=info['points'][0]['p'][0]; y=info['points'][0]['p'][1]
        click(c,x,y)
        print('after-center',json.dumps(state(c),ensure_ascii=False))
finally:
    c.close()
