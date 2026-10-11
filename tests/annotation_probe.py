import sys
import time

sys.path.insert(0, "tests")
from device import connect, evaluate, protocol


def code_value(value):
    return {"F8": 119, "F10": 121, "Enter": 13, "Escape": 27}[value]


def key(client, value, code):
    for event in ("keyDown", "keyUp"):
        protocol(client, "Input.dispatchKeyEvent", {
            "type": event,
            "key": value,
            "code": code,
            "windowsVirtualKeyCode": code_value(value),
            "nativeVirtualKeyCode": code_value(value),
        })


def state(client):
    return evaluate(client, """({
      url: location.pathname,
      menu: !!document.getElementById('wr-hh-menu'),
      ann: document.querySelectorAll('.wr-hh-annotation').length,
      marked: document.querySelectorAll('[data-wr-hh-annotation]').length,
      diag: document.getElementById('wr-diag') && document.getElementById('wr-diag').textContent,
      loading: !!document.getElementById('wr-hh-loading'),
      hint: document.getElementById('wr-hh-hint') && document.getElementById('wr-hh-hint').textContent,
      active: document.activeElement && (document.activeElement.className || document.activeElement.tagName)
    })""")


client = connect()
try:
    print("pre", state(client))
    key(client, "F10", "F10")
    time.sleep(0.5)
    print("f10", state(client))
    key(client, "Escape", "Escape")
    time.sleep(0.4)
    key(client, "F8", "F8")
    time.sleep(0.5)
    print("f8", state(client))
finally:
    client.close()
