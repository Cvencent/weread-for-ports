"""Back up and atomically deploy the current WeRead runtime files."""
import hashlib
from pathlib import Path
import time

from device import command, connect, evaluate


FILES = {
    "extension/content.js": "/storage/.config/weread-ext/content.js",
    "extension/background-v8.1.js": "/storage/.config/weread-ext/background-v8.1.js",
    "extension/shell.css": "/storage/.config/weread-ext/shell.css",
    "extension/manifest.json": "/storage/.config/weread-ext/manifest.json",
    "extension/telemetry-rules.json": "/storage/.config/weread-ext/telemetry-rules.json",
    "launcher/node.sh": "/storage/roms/ports/weread/node.sh",
    "launcher/window_guard.py": "/storage/roms/ports/weread/window_guard.py",
    "launcher/input_bridge.py": "/storage/roms/ports/weread/input_bridge.py",
    "launcher/cdp.py": "/storage/roms/ports/browser/cdp.py",
    "launcher/weread.gptk": "/storage/roms/ports/browser/weread.gptk",
    "launcher/操作说明.txt": "/storage/roms/ports/browser/操作说明.txt",
    "ports/media/Weread.png": "/storage/roms/ports/media/Weread.png",
}


def main():
    root = Path(__file__).resolve().parents[1]
    files = {root / relative: remote for relative, remote in FILES.items()}
    client = connect()
    backup = "/storage/.config/weread-ui-backups/" + time.strftime("%Y%m%d-%H%M%S")
    try:
        command(client, "mkdir -p " + backup)
        with client.open_sftp() as sftp:
            for source, remote in files.items():
                try:
                    command(client, "cp " + remote + " " + backup + "/" + source.name)
                except RuntimeError:
                    # Files that a device may legitimately not have yet, so a
                    # missing backup must not abort the whole deployment. cdp.py
                    # joins this set because older installs never shipped it.
                    optional = {"window_guard.py", "input_bridge.py", "cdp.py",
                                "background-v8.1.js", "shell.css", "Weread.png",
                                "telemetry-rules.json"}
                    if source.name not in optional:
                        raise
                data = source.read_bytes().replace(b"\r\n", b"\n")
                with sftp.file(remote + ".weread-new", "wb") as target:
                    target.write(data)
                mode = 0o755 if source.name.endswith((".sh", ".py")) else 0o644
                sftp.chmod(remote + ".weread-new", mode)
            command(client, "bash -n /storage/roms/ports/weread/node.sh.weread-new")
            for source, remote in files.items():
                sftp.posix_rename(remote + ".weread-new", remote)
                with sftp.file(remote, "rb") as target:
                    installed = target.read()
                expected = source.read_bytes().replace(b"\r\n", b"\n")
                assert hashlib.sha256(installed).digest() == hashlib.sha256(expected).digest()
                print("verified", source.name, len(installed))
        print("backup", backup)
        print(command(client, "systemctl stop wr-ui-v8-baseline.service wr-ui-v8.service "
                              "2>/dev/null || true"))
        print(command(client, "systemd-run --unit=wr-ui-v8 "
                              "--property=BindsTo=essway.service --collect "
                              "/storage/roms/ports/weread/node.sh"))
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            try:
                if evaluate(client, """!!document.getElementById('wr-hh-nav') &&
                    !!document.querySelector('.shelfBook') &&
                    document.querySelector('.shelfBook').getBoundingClientRect().height>80"""):
                    print("ready", evaluate(client, "[innerWidth,innerHeight]"))
                    break
            except RuntimeError:
                pass
            time.sleep(0.5)
        else:
            raise RuntimeError("Browser did not reach its ready shelf within 40 seconds")
    finally:
        client.close()


if __name__ == "__main__":
    main()
