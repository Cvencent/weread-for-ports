import json, sys, time, base64
sys.path.insert(0, 'tests')
from device import connect, command, protocol, evaluate
c = connect()
try:
    # Start tracing in a separate remote helper so events can be written on device.
    remote = r'''
import sys,base64,json,time
sys.path.insert(0,"/storage/roms/ports/browser")
import cdp
ws=cdp.WS(cdp.pick_page_target()["webSocketDebuggerUrl"])
ws.call(1,"Tracing.start",{"categories":"devtools.timeline,v8,blink,cc,gpu,renderer.scheduler","transferMode":"ReturnAsStream"})
time.sleep(15)
res=ws.call(2,"Tracing.end",{})
print(json.dumps(res))
ws.close()
'''
    data=base64.b64encode(remote.encode()).decode()
    print(command(c, f"printf '%s' '{data}' | base64 -d | python3", timeout=60).strip())
finally:
    c.close()