"""Record the final installed files and the actual clean shelf window."""
import hashlib
import json
from pathlib import Path

from device import command, connect, evaluate
from e2e import OUT, capture, wait_for


ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "extension/content.js": "/storage/.config/weread-ext/content.js",
    "extension/background-v8.1.js": "/storage/.config/weread-ext/background-v8.1.js",
    "extension/shell.css": "/storage/.config/weread-ext/shell.css",
    "extension/manifest.json": "/storage/.config/weread-ext/manifest.json",
    "extension/telemetry-rules.json": "/storage/.config/weread-ext/telemetry-rules.json",
    "launcher/node.sh": "/storage/roms/ports/weread/node.sh",
    "launcher/window_guard.py": "/storage/roms/ports/weread/window_guard.py",
    "launcher/input_bridge.py": "/storage/roms/ports/weread/input_bridge.py",
    "launcher/weread.gptk": "/storage/roms/ports/browser/weread.gptk",
    "launcher/操作说明.txt": "/storage/roms/ports/browser/操作说明.txt",
    "ports/media/Weread.png": "/storage/roms/ports/media/Weread.png",
}

client = connect()
try:
    wait_for(client, "location.pathname==='/web/shelf' && !!document.querySelector('#wr-hh-nav') && !!document.querySelector('.wr-hh-focus')")
    wait_for(client, """Array.from(document.querySelectorAll('.shelfBook')).slice(0,8)
      .every(e=>{var i=e.querySelector('img');return i&&i.complete&&i.naturalWidth>0;})""")
    state = evaluate(client, """(function(){
      var books=Array.from(document.querySelectorAll('.shelfBook[href*="/web/reader/"]'));
      return {url:location.href,viewport:[innerWidth,innerHeight],
        completeBooks:books.filter(e=>{var r=e.getBoundingClientRect();return r.top>=56&&r.bottom<=innerHeight+1;}).length};
    })()""")
    assert state["viewport"] == [640, 480] and state["completeBooks"] >= 8, state
    tree = json.loads(command(client, "SWAYSOCK=/var/run/0-runtime-dir/sway-ipc.0.sock swaymsg -t get_tree -r"))
    windows = []

    def walk(node):
        if (node.get("app_id") or "").startswith("chrome-weread.qq.com__"):
            windows.append(node)
        for child in node.get("nodes", []) + node.get("floating_nodes", []):
            walk(child)

    walk(tree)
    assert len(windows) == 1
    window = windows[0]
    assert window["focused"] and window["fullscreen_mode"] in (1, 2)
    assert [window["rect"]["width"], window["rect"]["height"]] == [640, 480]
    state["window"] = {k: window[k] for k in ("id", "app_id", "focused", "fullscreen_mode", "rect")}
    state["files"] = {}
    with client.open_sftp() as sftp:
        for relative, remote in FILES.items():
            expected = (ROOT / relative).read_bytes().replace(b"\r\n", b"\n")
            with sftp.file(remote, "rb") as installed:
                actual = installed.read()
            assert hashlib.sha256(actual).digest() == hashlib.sha256(expected).digest(), relative
            state["files"][relative] = hashlib.sha256(actual).hexdigest()
    state["essway"] = command(client, "systemctl is-active essway.service").strip()
    assert state["essway"] == "active"
    capture(client, "v9-final-shelf.png")
    (OUT / "v9-final-state-evidence.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print("PASS final shelf 640x480, focused fullscreen, eight books, installed SHA256 and ES active", flush=True)
finally:
    client.close()
