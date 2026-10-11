import sys
sys.path.insert(0,'tests')
from device import connect,command
c=connect()
try:
    print(command(c,"""curl -sS -m 10 -X POST -H 'X-Weread-Input: v8' -H 'Content-Type: application/json' -d '{"action":"annotation"}' http://127.0.0.1:9223/action; echo; tail -80 /storage/roms/ports/browser/input-bridge.log"""))
finally:
    c.close()
