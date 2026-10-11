import json, sys, time
sys.path.insert(0, 'tests')
from device import connect, command, evaluate
c = connect()
try:
    print('PID_MAP')
    print(command(c, "cat /proc/964787/status | grep -E 'Name|VmRSS|Threads'; tr '\\0' ' ' < /proc/964787/cmdline; echo").strip())
    expr = r"""
(()=>{
  const timers = new Map(), rafs = [], observers = [], listeners = [];
  const origSI = window.setInterval, origST = window.setTimeout, origRAF = window.requestAnimationFrame, origMO = window.MutationObserver, origOAEL = EventTarget.prototype.addEventListener;
  window.__perf = {ticks:{interval:0,timeout:0,raf:0}, mutations:0, events:{}, byStack:{}};
  window.setInterval = function(fn, ms, ...a){ const id=origSI.call(this,(...x)=>{window.__perf.ticks.interval++; window.__perf.byStack[(new Error()).stack.split('\\n')[2]||'?']=(window.__perf.byStack[(new Error()).stack.split('\\n')[2]||'?']||0)+1; return fn(...x)},ms,...a); return id; };
  window.setTimeout = function(fn, ms, ...a){ const id=origST.call(this,(...x)=>{window.__perf.ticks.timeout++; return fn(...x)},ms,...a); return id; };
  window.requestAnimationFrame = function(fn){window.__perf.ticks.raf++; return origRAF.call(window,fn)};
  window.MutationObserver = class extends origMO { constructor(fn){super(fn)} };
  EventTarget.prototype.addEventListener = function(type,fn,opt){window.__perf.events[type]=(window.__perf.events[type]||0)+1; return origOAEL.call(this,type,fn,opt)};
  return true;
})()
"""
    evaluate(c, expr)
    time.sleep(10)
    print('PAGE_PERF', json.dumps(evaluate(c, "window.__perf"), ensure_ascii=False, indent=2)[:10000])
    print('COUNTERS', evaluate(c, "({raf:window.__perf.ticks.raf,interval:window.__perf.ticks.interval,timeouts:window.__perf.ticks.timeout,events:window.__perf.events})"))
    print('LONGTASKS_AVAILABLE', evaluate(c,"typeof PerformanceObserver!=='undefined'"))
finally:
    c.close()