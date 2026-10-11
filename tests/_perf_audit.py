import sys, time
sys.path.insert(0, 'tests')
from device import connect, command, evaluate
c = connect()
try:
    print('UPTIME', command(c, 'uptime').strip())
    print('MEM', command(c, 'free -m').strip())
    print('LOAD', command(c, 'cat /proc/loadavg').strip())
    print('PAGE', evaluate(c, "({url:location.pathname,reader:/\\/web\\/reader\\//.test(location.pathname),canvas:document.querySelectorAll('canvas').length})"))
    print('PROCS')
    print(command(c, "ps -eo pid,ppid,pcpu,pmem,rss,comm,args --sort=-pcpu | head -25").strip())
finally:
    c.close()