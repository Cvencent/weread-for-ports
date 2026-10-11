import sys,time
sys.path.insert(0,"tests")
from device import connect, evaluate, protocol
c=connect()
try:
    evaluate(c, "window.__keylog=[];document.addEventListener('keydown',function(e){window.__keylog.push([e.key,e.code,e.keyCode,e.isTrusted]);},true);void 0")
    evaluate(c, "document.dispatchEvent(new KeyboardEvent('keydown',{key:'F8',code:'F8',keyCode:119,which:119,bubbles:true,cancelable:true}));void 0")
    time.sleep(.3)
    print("synthetic", evaluate(c,"window.__keylog"))
    for t in ("keyDown","keyUp"):
        protocol(c,"Input.dispatchKeyEvent",{"type":t,"key":"F8","code":"F8","windowsVirtualKeyCode":119,"nativeVirtualKeyCode":119})
    time.sleep(.3)
    print("trusted", evaluate(c,"window.__keylog"))
finally:
    c.close()
