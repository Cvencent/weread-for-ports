"""Device helpers for real handheld acceptance tests.

Credentials come from the environment, or from a git-ignored `.device.env`
file in the repository root, so a real handheld does not have to be re-typed
in every session. That file stays local on purpose: it holds a password.
"""
import argparse
import base64
import json
import os
from pathlib import Path

import paramiko

LOCAL_ENV = Path(__file__).resolve().parent.parent / ".device.env"


def load_local_env(path=LOCAL_ENV):
    """Read the WEREAD_* keys from a local `.device.env` file.

    A missing file is normal; it just means this checkout has no device yet.
    """
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return {}
    loaded = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip(chr(39) + chr(34))
        if key.startswith("WEREAD_") and value:
            loaded[key] = value
    return loaded


LOCAL = load_local_env()


def setting(name, default=None):
    """Read one connection setting, environment first, then `.device.env`.

    Falling back to the file on every lookup rather than only at import time
    keeps the device configured even if something else in the process clears
    the environment, which would otherwise skip the real-hardware tests.
    """
    value = os.environ.get(name)
    if value:
        return value
    return LOCAL.get(name, default)


def missing_credentials():
    """True when the handheld is not configured for this run.

    Device tests are real-hardware acceptance tests, so they cannot run in a
    checkout that has no credentials. Callers should skip instead of erroring:
    a missing device is a skipped test, not a broken one.
    """
    return not (setting("WEREAD_HOST") and setting("WEREAD_PASSWORD"))


def connect(host=None, username=None, password=None, port=None):
    host = host or setting("WEREAD_HOST")
    username = username or setting("WEREAD_USER", "root")
    password = password or setting("WEREAD_PASSWORD")
    if not host or not password:
        raise ValueError("Set WEREAD_HOST and WEREAD_PASSWORD in the environment "
                         "or put them in a .device.env file next to the repository")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, port=int(port or setting("WEREAD_SSH_PORT", "22")),
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
sys.path.insert(0,"/storage/roms/ports/weread")
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
