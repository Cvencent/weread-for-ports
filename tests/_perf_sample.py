import json, sys, time
sys.path.insert(0, 'tests')
from device import connect, command, evaluate, protocol
c = connect()
try:
    evaluate(c, "location.href='https://weread.qq.com/web/shelf';void 0")
    time.sleep(5)
    metrics = ["TaskDuration","ScriptDuration","LayoutDuration","RecalcStyleDuration","JSHeapUsedSize","JSHeapTotalSize","Nodes","Documents","Frames","LayoutCount","RecalcStyleCount"]
    protocol(c, "Performance.enable", {})
    def sample():
        raw = protocol(c, "Performance.getMetrics", {}).get("metrics", [])
        return {x["name"]: x["value"] for x in raw if x["name"] in metrics}
    before = sample()
    raf = evaluate(c, """new Promise(resolve=>{var n=0,t0=performance.now(),last=t0,max=0;function f(t){n++;max=Math.max(max,t-last);last=t;if(t-t0>3000)resolve({frames:n,ms:t-t0,fps:n*1000/(t-t0),maxGap:max});else requestAnimationFrame(f)}requestAnimationFrame(f)})""")
    time.sleep(12)
    after = sample()
    print(json.dumps({"page": evaluate(c,"({url:location.pathname,visibility:document.visibilityState,animations:document.getAnimations().map(a=>({name:a.animationName||'',state:a.playState,target:(a.effect&&a.effect.target&&a.effect.target.className)||''})).slice(0,40),nodes:document.getElementsByTagName('*').length})"),"raf":raf,"delta":{k:round(after.get(k,0)-before.get(k,0),4) for k in metrics}}, ensure_ascii=False, indent=2))
    print("TOP")
    print(command(c,"top -b -n 3 -d 2 | grep -E 'chrome|gptokeyb|sway|emulationstation|PID' | tail -30").strip())
finally:
    c.close()