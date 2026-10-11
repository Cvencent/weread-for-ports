import sys,json
sys.path.insert(0,'tests')
from device import connect,command,evaluate
c=connect()
try:
    print(evaluate(c,"({url:location.pathname,loading:!!document.getElementById('wr-hh-loading'),menu:!!document.getElementById('wr-hh-menu'),kbd:!!document.getElementById('wr-hh-kbd'),overlay:!!document.getElementById('wr-hh-overlay'),focus:(document.querySelector('.wr-hh-focus')||{}).innerText||null,shelf:document.querySelectorAll('.shelfBook').length})"))
    print('gptokeyb:',command(c,"pgrep -a gptokeyb || true").strip())
    print('guard procs:',command(c,"ps -eo pid,ppid,comm,args | grep node.sh | grep -v grep").strip())
    print('essway:',command(c,'systemctl is-active essway.service').strip())
finally:
    c.close()