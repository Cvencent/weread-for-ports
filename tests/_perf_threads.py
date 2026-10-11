import sys, time, json
sys.path.insert(0, 'tests')
from device import connect, command, evaluate, protocol
c = connect()
try:
    pid = command(c, "ps -eo pid,args | grep 'type=renderer' | grep 'renderer-client-id=6' | awk '{print $1}' | head -1").strip()
    print('renderer_pid', pid)
    print(command(c, f"top -H -b -n 3 -d 2 -p {pid} | head -80").strip())
    print('metrics_raw', protocol(c, 'Performance.getMetrics', {}))
finally:
    c.close()