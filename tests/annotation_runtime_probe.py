import sys,time,json
sys.path.insert(0,'tests')
from device import connect,evaluate,protocol
c=connect()
expr="""(function(){
var r=document.querySelector('.wr_horizontalReader,.readerChapterContent_container');
var rr=r&&r.getBoundingClientRect();
return {path:location.pathname,reader:!!r,readerShown:!!(r&&rr.width>=18&&rr.height>=14),readerRect:r?[rr.left,rr.top,rr.width,rr.height]:null,underlines:document.querySelectorAll('.wr_underline_wrapper').length,diag:document.getElementById('wr-diag')&&document.getElementById('wr-diag').textContent,menu:!!document.getElementById('wr-hh-menu'),loading:!!document.getElementById('wr-hh-loading'),activeTag:document.activeElement&&document.activeElement.tagName,adv:document.activeElement&&document.activeElement.getAttribute('contenteditable'),bodyClass:document.body.className};
})()"""
print('before',json.dumps(evaluate(c,expr),ensure_ascii=False))
for t in ('keyDown','keyUp'):
    protocol(c,'Input.dispatchKeyEvent',{'type':t,'key':'F8','code':'F8','windowsVirtualKeyCode':119,'nativeVirtualKeyCode':119})
time.sleep(.4)
print('after-f8',json.dumps(evaluate(c,expr),ensure_ascii=False))
print('ann',json.dumps(evaluate(c,"Array.from(document.querySelectorAll('.wr_underline_wrapper')).map(e=>({cls:e.className,data:e.getAttribute('data-wr-hh-annotation'),rect:(function(r){return [r.left,r.top,r.width,r.height]})(e.getBoundingClientRect())}))"),ensure_ascii=False))
c.close()
