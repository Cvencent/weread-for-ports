import json, sys, time
sys.path.insert(0, 'tests')
from device import connect, command, evaluate
c = connect()
try:
    print('GUARD_PROCS')
    print(command(c, "ps -eo pid,ppid,pcpu,etime,comm,args | grep -E 'window_guard|watchdog|focusguard|fullguard|node.sh|bash' | grep -v grep").strip())
    # Sample process CPU over two readings; report child wakeups for node.sh tree.
    print('NODE_TREE')
    print(command(c, "ps -ef | grep -E 'node.sh|window_guard|focusguard|fullguard|watchdog' | grep -v grep").strip())
    print('PAGE_INTERVAL_STATE')
    # Extension is isolated; sample page performance counters and long tasks, not implementation counters.
    script = """
    new Promise(resolve=>{let long=[];let po=new PerformanceObserver(l=>{for(const e of l.getEntries())long.push(e.duration)});try{po.observe({type:'longtask'})}catch(e){}let n=0,t0=performance.now(),last=t0,max=0;function f(t){n++;max=Math.max(max,t-last);last=t;if(t-t0>8000){po.disconnect();resolve({frames:n,ms:t-t0,fps:n*1000/(t-t0),maxGap:max,longTasks:long});}else requestAnimationFrame(f)}requestAnimationFrame(f)})
    """
    print('RAF', json.dumps(evaluate(c, script), ensure_ascii=False))
finally:
    c.close()