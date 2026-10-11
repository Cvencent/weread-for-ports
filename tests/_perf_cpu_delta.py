import sys,time,json,re
sys.path.insert(0,'tests')
from device import connect,command,evaluate
c=connect()
try:
    # Snapshot CPU jiffies for renderer/process tree before and after 30s idle.
    def cpu_snapshot():
        out=command(c,"ps -eo pid,ppid,comm,args | grep -E 'chrome|gptokeyb|node.sh|sway' | grep -v grep")
        # use /proc/stat + per-pid ticks via ps -o times
        return command(c,"ps -eo pid,comm,times,time,pcpu,rss --sort=-times | head -20")
    print('before')
    print(cpu_snapshot())
    time.sleep(30)
    print('after')
    print(cpu_snapshot())
    print('free',command(c,'free -m').strip())
finally:
    c.close()