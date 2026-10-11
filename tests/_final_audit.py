import sys
sys.path.insert(0, "tests")
from device import connect, command, evaluate
c = connect()
try:
    print("gptokeyb:", command(c, "pgrep -a gptokeyb || true").strip())
    print("essway:", command(c, "systemctl is-active essway.service").strip())
    print("state:", evaluate(c, "({url:location.pathname,loading:!!document.getElementById('wr-hh-loading'),menu:!!document.getElementById('wr-hh-menu'),kbd:!!document.getElementById('wr-hh-kbd'),overlay:!!document.getElementById('wr-hh-overlay'),focus:(document.querySelector('.wr-hh-focus')||{}).innerText||null,shelf:document.querySelectorAll('.shelfBook').length})"))
finally:
    c.close()