import sys,time,json
sys.path.insert(0,'tests')
from device import connect,command,evaluate
c=connect()
try:
    def snap():
        return command(c,"ps -eo pid,comm,times,rss --sort=-times | head -16")
    print('before'); print(snap())
    time.sleep(30)
    print('after'); print(snap())
    print('guards'); print(command(c,"ps -eo pid,ppid,times,comm,args | grep -E 'node.sh|window_guard|watchdog|focusguard|fullguard' | grep -v grep").strip())
    print('page',evaluate(c,"({url:location.pathname,nodes:document.getElementsByTagName('*').length,animations:document.getAnimations().length,loading:!!document.getElementById('wr-hh-loading')})"))
    raf=evaluate(c,"new Promise(resolve=>{let n=0,t0=performance.now(),last=t0,max=0;function f(t){n++;max=Math.max(max,t-last);last=t;if(t-t0>5000)resolve({frames:n,ms:t-t0,fps:n*1000/(t-t0),maxGap:max});else requestAnimationFrame(f)}requestAnimationFrame(f)})")
    print('raf',json.dumps(raf))
finally:
    c.close()