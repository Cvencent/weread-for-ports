import sys
sys.path.insert(0,'tests')
from device import connect,command
c=connect()
try:
    print(command(c,"ps -eo pid,ppid,rss,vsz,comm,args | grep chrome | grep -v grep | sort -k3 -nr | head -15"))
    print(command(c,'free -m'))
finally:
    c.close()