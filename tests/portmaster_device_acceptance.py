"""Accept the PortMaster install path on a real handheld.

PortMaster never runs install.sh: it unpacks weread.zip into the ports folder
and the frontend runs the top-level Weread.sh. Every step of that path is
invisible to the desktop suite -- the zip has to survive PortMaster's own
check_port(), land with usable permissions, and bootstrap its own cover and
gamelist entry on first launch -- so it is driven here against the real device,
using PortMaster's own installer rather than a lookalike that could disagree.

    python tests/portmaster_device_acceptance.py
"""
import base64
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from device import connect, missing_credentials

ROOT = Path(__file__).resolve().parents[1]
PORTS = "/storage/roms/ports"
PM = PORTS + "/PortMaster"
ZIP = ROOT / "output" / "weread.zip"
REMOTE_ZIP = PM + "/autoinstall/weread.zip"

# What the zip promises, and therefore what has to exist after the install.
INSTALLED = [
    "Weread.sh",
    "weread/port.json",
    "weread/node.sh",
    "weread/window_guard.py",
    "weread/input_bridge.py",
    "weread/cdp.py",
    "weread/weread.gptk",
    "weread/Weread.png",
    "weread/update_gamelist.py",
    "weread/gamelist.fragment.xml",
    "weread/ext/content.js",
    "weread/ext/shell.css",
    "weread/ext/manifest.json",
    "weread/ext/background-v8.1.js",
    "weread/ext/telemetry-rules.json",
]

failures = []


def check(label, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + label + ((" :: " + str(detail)) if detail else ""))
    if not ok:
        failures.append(label)
    return ok


def probe(client, text, timeout=120):
    """device.command() for questions whose answer is allowed to be nonzero.

    "Is this running?" and "does this file exist?" both answer with an exit
    status, and treating that as an exception would abort the run before it
    reported anything useful.
    """
    _, stdout, stderr = client.exec_command(text, timeout=timeout)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    return (out + err).strip()


def push_script(client, body, path="/tmp/weread-acceptance.py"):
    """Ship a script over as base64; the device shell mangles quoting otherwise."""
    data = base64.b64encode(body.encode("utf-8")).decode()
    probe(client, "printf '%s' '" + data + "' | base64 -d > " + path)
    return path


def teardown(client):
    """Wipe every trace of an earlier install so this really is a first run."""
    probe(client, "pkill -f '[c]hrome --' || true")
    probe(client, "pkill -x gptokeyb || true")
    probe(client, "rm -rf /tmp/weread.lockdir /tmp/weread.pid")
    # The entry has to go before the directory that holds the updater goes.
    probe(client, "python3 " + PORTS + "/weread/update_gamelist.py " +
          PORTS + "/gamelist.xml --remove >/dev/null 2>&1 || true")
    probe(client, "rm -rf " + PORTS + "/weread " + PORTS + "/Weread.sh")
    probe(client, "rm -f " + PORTS + "/media/Weread.png " + REMOTE_ZIP)
    time.sleep(1)


def install(client):
    """Install with PortMaster's own harbourmaster, from a local zip file."""
    body = """
import sys
sys.path.insert(0, "%(pm)s")
sys.path.insert(0, "%(pm)s/pylibs")
sys.path.insert(0, "%(pm)s/exlibs")
from pylibs.harbourmaster.harbour import HarbourMaster
hm = HarbourMaster(config={"offline": True})
print("INSTALL_RC", hm.install_port("%(zip)s"))
""" % {"pm": PM, "zip": REMOTE_ZIP}
    path = push_script(client, body)
    return probe(client, "cd " + PM + " && python3 " + path + " 2>&1 | tail -5")


def count(client, pattern):
    """How many processes match, without pgrep matching the probe itself.

    The bracket in the pattern is what keeps the pgrep command line from
    showing up in its own results.
    """
    return int(probe(client, "pgrep -f '" + pattern + "' | wc -l").strip() or 0)


def chrome_count(client):
    return count(client, "[c]hrome --")


def fire(client, text, seconds=5):
    """Start something that is meant to keep running, without waiting for it.

    Reading the channel to EOF would block for as long as the app lives: the
    backgrounded launcher inherits the SSH channel's stdout, so the far end
    never closes. Detach, give the shell a moment, and move on.
    """
    channel = client.get_transport().open_session()
    channel.exec_command(text)
    deadline = time.time() + seconds
    while time.time() < deadline and not channel.exit_status_ready():
        time.sleep(0.2)
    channel.close()


def launch(client):
    """Start the port the way the frontend does: run the top-level launcher."""
    fire(client, "cd " + PORTS +
         " && setsid ./Weread.sh >/tmp/weread-acceptance.log 2>&1 </dev/null &")
    deadline = time.time() + 120
    while time.time() < deadline:
        if chrome_count(client):
            break
        time.sleep(2)
    time.sleep(8)


def main():
    if missing_credentials():
        print("no handheld configured: set WEREAD_HOST and WEREAD_PASSWORD")
        return 2
    if not ZIP.is_file():
        print("missing " + str(ZIP) + "; run: python tests/package_portmaster.py")
        return 2

    client = connect()
    try:
        print("== teardown ==")
        teardown(client)
        check("previous install is gone",
              not probe(client, "ls " + PORTS + "/weread 2>/dev/null || true") and
              not probe(client, "test -f " + PORTS + "/Weread.sh && echo yes || true"))

        print("== autoinstall zip in place ==")
        client.open_sftp().put(str(ZIP), REMOTE_ZIP)
        check("weread.zip staged for autoinstall",
              probe(client, "ls -l " + REMOTE_ZIP + " | awk '{print $5}'") ==
              str(ZIP.stat().st_size))

        print("== install through PortMaster ==")
        print(probe(client, "ls -l " + REMOTE_ZIP))
        output = install(client)
        print(output)
        check("harbourmaster accepted the port", "INSTALL_RC 0" in output, output)

        print("== installed tree ==")
        listing = probe(client, "cd " + PORTS + " && ls -l Weread.sh weread weread/ext")
        print(listing)
        for name in INSTALLED:
            mode = probe(client, "stat -c '%a' " + PORTS + "/" + name + " 2>/dev/null || echo missing")
            check(name + " landed with mode " + mode, mode not in ("missing", ""), mode)

        print("== PortMaster metadata ==")
        info = json.loads(probe(client, "cat " + PORTS + "/weread/port.json"))
        check("title survived the round trip", info["attr"]["title"] == "\u5fae\u4fe1\u8bfb\u4e66",
              info["attr"]["title"])
        check("cover path points inside the package",
              info["attr"]["image"]["Weread.png"] == "weread/Weread.png")
        check("architecture is not gated", info["attr"]["arch"] == [], info["attr"]["arch"])

        print("== first launch ==")
        launch(client)
        check("chromium is up", chrome_count(client) > 0, chrome_count(client))
        version = probe(client, "python3 -c \"import urllib.request;"
                        "print(urllib.request.urlopen('http://127.0.0.1:9222/json/version',"
                        "timeout=5).read().decode())\" 2>&1")
        check("CDP is listening", "webSocketDebuggerUrl" in version, version[:120])
        check("exactly one gptokeyb", count(client, "[g]ptokeyb") == 1,
              probe(client, "pgrep -af '[g]ptokeyb' || true"))
        check("cover published to the shared media folder",
              probe(client, "stat -c '%s' " + PORTS + "/media/Weread.png 2>/dev/null || echo missing")
              not in ("missing", "0"))
        gamelist = probe(client, "grep -A3 'Weread.sh' " + PORTS + "/gamelist.xml || true")
        print(gamelist)
        check("gamelist entry registered on its own", "Weread.sh" in gamelist)
        check("entry is the Chinese title", "\u5fae\u4fe1\u8bfb\u4e66" in gamelist)
        check("entry points at the published cover", "./media/Weread.png" in gamelist)
        check("login profile preserved",
              probe(client, "test -d /storage/.config/weread-profile && echo yes || echo no")
              == "yes")

        shot = Path("output/portmaster-acceptance.png")
        shot.parent.mkdir(parents=True, exist_ok=True)
        probe(client, "XDG_RUNTIME_DIR=/var/run/0-runtime-dir WAYLAND_DISPLAY=wayland-1 "
                      "grim /tmp/weread-acceptance.png")
        with client.open_sftp() as sftp:
            sftp.get("/tmp/weread-acceptance.png", str(shot))
        print("screenshot", shot.resolve())

        print("== launcher log tail ==")
        print(probe(client, "tail -15 " + PORTS + "/weread/weread.log 2>/dev/null || true"))
    finally:
        client.close()

    print()
    if failures:
        print("FAILED: " + ", ".join(failures))
        return 1
    print("PortMaster install path accepted end to end")
    return 0


if __name__ == "__main__":
    sys.exit(main())
