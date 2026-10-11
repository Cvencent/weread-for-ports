import sys,time,json,base64
sys.path.insert(0,'tests')
from device import connect,command
c=connect()
try:
    remote=r'''
import sys,json,time
sys.path.insert(0,"/storage/roms/ports/browser")
import cdp
ws=cdp.WS(cdp.pick_page_target()["webSocketDebuggerUrl"])
def call(i,m,p={}): return ws.call(i,m,p)
call(1,"Tracing.start",{"categories":"devtools.timeline,v8,blink,cc,gpu,renderer.scheduler","transferMode":"ReturnAsStream"})
time.sleep(15)
r=call(2,"Tracing.end",{})
stream=r.get("result",{}).get("stream")
if not stream:
 print(json.dumps({"error":"no stream","response":r})); raise SystemExit
chunks=[]
i=3
while True:
 x=call(i,"IO.read",{"handle":stream,"size":1048576}); i+=1
 chunks.append(x.get("result",{}).get("data",""))
 if x.get("result",{}).get("eof"): break
call(i,"IO.close",{"handle":stream})
data="".join(chunks)
print(json.dumps({"bytes":len(data),"head":data[:200]}))
open("/tmp/wr-trace.json","w").write(data)
ws.close()
'''
    data=base64.b64encode(remote.encode()).decode()
    print(command(c,f"printf '%s' '{data}' | base64 -d | python3",timeout=60).strip())
    # summarize on device using a compact script
    remote2=r'''
import json,collections,sys
ev=json.load(open("/tmp/wr-trace.json")).get("traceEvents",[])
agg=collections.defaultdict(lambda:[0,0.0])
for e in ev:
 if e.get("ph")!="X": continue
 n=e.get("name",""); dur=e.get("dur",0)
 a=agg[n]; a[0]+=1; a[1]+=dur
rows=[]
for n,(cnt,dur) in agg.items():
 us=dur
 if us>=100 or cnt>10: rows.append((round(us/1000,2),cnt,n))
for x in sorted(rows,reverse=True)[:25]: print(x)
'''
    data2=base64.b64encode(remote2.encode()).decode()
    print(command(c,f"printf '%s' '{data2}' | base64 -d | python3",timeout=60).strip())
finally:
    c.close()