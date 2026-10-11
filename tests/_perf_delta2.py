import sys,time,json
sys.path.insert(0,'tests')
from device import connect,command
c=connect()
try:
    def tick(expr):
        out=command(c,expr).strip().split()
        return int(out[0]) if out and out[0].isdigit() else 0
    node_expr="p=$(pgrep -f '/storage/roms/ports/weread/node.sh' | head -1); if [ -n \"$p\" ]; then awk '{print $14+$15}' /proc/$p/stat; else echo 0; fi"
    rend_expr="p=$(ps -eo pid,args | awk '/type=renderer/ && !/awk/ {print $1; exit}'); if [ -n \"$p\" ]; then awk '{print $14+$15}' /proc/$p/stat; else echo 0; fi"
    gp_expr="p=$(pgrep -x gptokeyb | head -1); if [ -n \"$p\" ]; then awk '{print $14+$15}' /proc/$p/stat; else echo 0; fi"
    before=(tick(node_expr),tick(rend_expr),tick(gp_expr))
    time.sleep(30)
    after=(tick(node_expr),tick(rend_expr),tick(gp_expr))
    print(json.dumps({'before':before,'after':after,'delta':{k:b-a for k,a,b in zip(('node','renderer','gptokeyb'),before,after)},'hz':100},ensure_ascii=False))
    print(command(c,'free -m').strip())
finally:
    c.close()