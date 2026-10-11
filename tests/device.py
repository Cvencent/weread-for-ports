"""Device helpers for real handheld acceptance tests.

Set WEREAD_HOST and WEREAD_PASSWORD before running the scripts.
"""
import argparse
import base64
import json
import os
from pathlib import Path

import paramiko


def missing_credentials():
    """True when the handheld is not configured for this run.

    Device tests are real-hardware acceptance tests, so they cannot run in a
    checkout that has no credentials. Callers should skip instead of erroring:
    a missing device is a skipped test, not a broken one.
    """
    return not (os.environ.get("WEREAD_HOST") and os.environ.get("WEREAD_PASSWORD"))


def connect(host=None, username=None, password=None, port=None):
    host = host or os.environ.get("WEREAD_HOST")
    username = username or os.environ.get("WEREAD_USER", "root")
    password = password or os.environ.get("WEREAD_PASSWORD")
    if not host or not password:
        raise ValueError("Set WEREAD_HOST and WEREAD_PASSWORD in the environment")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, port=int(port or os.environ.get("WEREAD_SSH_PORT", "22")),
                   username=username, password=password, timeout=12,
                   look_for_keys=False, allow_agent=False)
    return client


def command(client, text, timeout=45):
    _, stdout, stderr = client.exec_command(text, timeout=timeout)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    if stdout.channel.recv_exit_status():
        raise RuntimeError(err or out)
    return out


def protocol(client, method, params):
    payload = base64.b64encode(json.dumps({"method": method, "params": params}).encode()).decode()
    script = f"""
import sys,base64,json
sys.path.insert(0,"/storage/roms/ports/browser")
import cdp
ws=cdp.WS(cdp.pick_page_target()["webSocketDebuggerUrl"])
try:
 request=json.loads(base64.b64decode("{payload}"))
 response=ws.call(1,request["method"],request["params"])
 if "error" in response: raise RuntimeError(json.dumps(response["error"]))
 print(json.dumps(response.get("result",{{}}),ensure_ascii=False))
finally: ws.close()
"""
    data = base64.b64encode(script.encode()).decode()
    return json.loads(command(client, f"printf '%s' '{data}' | base64 -d | python3"))


def evaluate(client, expression):
    result = protocol(client, "Runtime.evaluate",
                      {"expression": expression, "returnByValue": True, "awaitPromise": True})
    if "exceptionDetails" in result:
        raise RuntimeError(json.dumps(result["exceptionDetails"]))
    return result.get("result", {}).get("value")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.environ.get("WEREAD_HOST"))
    parser.add_argument("--js")
    parser.add_argument("--expr")
    parser.add_argument("--key")
    parser.add_argument("--shot")
    parser.add_argument("--focus", action="store_true")
    args = parser.parse_args()
    client = connect(args.host)
    try:
        if args.focus:
            print(command(client, "SWAYSOCK=/var/run/0-runtime-dir/sway-ipc.0.sock swaymsg "
                                  "'[app_id=\"^chrome-weread\\.qq\\.com__.*\"] focus, fullscreen enable'"))
        if args.key:
            print(command(client, "python3 /storage/roms/ports/browser/vpad.py " + args.key))
        if args.js or args.expr:
            expression = Path(args.js).read_text(encoding="utf-8") if args.js else args.expr
            print(json.dumps(evaluate(client, expression), ensure_ascii=False, indent=2))
        if args.shot:
            command(client, "XDG_RUNTIME_DIR=/var/run/0-runtime-dir WAYLAND_DISPLAY=wayland-1 "
                            "grim /tmp/weread-ui.png")
            destination = Path(args.shot)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with client.open_sftp() as sftp:
                sftp.get("/tmp/weread-ui.png", str(destination))
            print(str(destination.resolve()))
    finally:
        client.close()


if __name__ == "__main__":
    main()
