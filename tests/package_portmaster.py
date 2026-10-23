"""Build weread.zip as a PortMaster port package.

PortMaster's installer (harbourmaster) expects a specific shape, which was read
off the real device rather than guessed:

  * the zip is flat -- there is no single wrapping directory, because
    check_port() in harbourmaster/harbour.py walks the top level and collects
    one directory plus every top-level ``.sh`` script;
  * at least one directory and at least one top-level ``.sh`` are mandatory or
    check_port() raises BadPort and the install aborts;
  * absolute paths and ``../`` traversal are rejected;
  * ``port.json`` is version 2 metadata (attr/title/desc/genres/porter/image).

The package has two shapes:

  weread.zip         the release: everything plus our own Chromium 154, NSS
                     libraries and a CJK font under weread/browser/, so a
                     novice installs one file and never installs a browser.
  weread-lite.zip    the same port without the ~500MB payload, for people who
                     already run a Browser port and want to point at it with
                     WEREAD_BROWSER_DIR.

The layout PortMaster installs:

  Weread.sh              top-level launcher -> extracted to the ports dir
  media/Weread.png       cover
  weread/                everything WeRead owns, self-contained
    port.json node.sh window_guard.py input_bridge.py cdp.py weread.gptk
    ext/content.js shell.css manifest.json background-v8.1.js telemetry-rules.json
    browser/             Chromium 154 + nss/ + fonts/ + MANIFEST.json
    操作说明.txt
"""
import hashlib
import json
from pathlib import Path
import stat
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "output" / "weread.zip"
LITE_ARCHIVE = ROOT / "output" / "weread-lite.zip"
DEFAULT_BROWSER_PAYLOAD = ROOT / "output" / "browser_payload"

# (source path in the repo, path inside the zip)
LAUNCHER_FILES = ["node.sh", "window_guard.py", "input_bridge.py", "cdp.py",
                  "weread.gptk", "操作说明.txt"]
EXTENSION_FILES = ["content.js", "shell.css", "manifest.json",
                   "background-v8.1.js", "telemetry-rules.json"]
# Shipped so the first launch can publish the cover and register the curated
# gamelist entry without anyone running install.sh.
BOOTSTRAP_FILES = [("ports/media/Weread.png", "weread/Weread.png"),
                   ("ports/update_gamelist.py", "weread/update_gamelist.py"),
                   ("ports/gamelist.fragment.xml", "weread/gamelist.fragment.xml")]

# The whole point of the release package: the browser travels with the port.
BROWSER_REQUIRED = ("chromium/chrome", "nss/libnss3.so",
                    "fonts/NotoSansSC-Regular.otf")


def entries():
    """Yield (absolute source path, path inside the zip) in a stable order."""
    yield ROOT / "ports" / "Weread.sh", "Weread.sh"
    yield ROOT / "ports" / "port.json", "weread/port.json"
    for name in LAUNCHER_FILES:
        yield ROOT / "launcher" / name, "weread/" + name
    for name in EXTENSION_FILES:
        yield ROOT / "extension" / name, "weread/ext/" + name
    for source_rel, arcname in BOOTSTRAP_FILES:
        yield ROOT / source_rel, arcname


def zip_mode(source, arcname):
    """Keep the executable bit on scripts, helpers and the chrome binary."""
    if source.suffix in (".sh", ".py") or arcname.endswith("chromium/chrome"):
        return 0o755
    if source.suffix == ".so" or ".so." in source.name:
        return 0o755
    return 0o644


def verify_browser_payload(payload):
    """Fail before shipping unless the payload is actually complete."""
    payload = Path(payload)
    if not payload.is_dir():
        sys.exit("browser payload not found: %s\n"
                 "build it first with: python tools/build_browser_payload.py" % payload)
    for required in BROWSER_REQUIRED:
        if not (payload / required).is_file():
            sys.exit("browser payload is incomplete: missing %s" % required)
    manifest = payload / "MANIFEST.json"
    if not manifest.is_file():
        sys.exit("browser payload has no MANIFEST.json; rebuild it")
    return payload


def validate(archive):
    """Re-check the package the way PortMaster does, so we fail before shipping.

    This mirrors the hard requirements of harbourmaster's check_port().
    """
    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()
        for name in names:
            assert not name.startswith("/"), name
            assert not name.startswith("../"), name
            assert "/../" not in name, name

        # check_port() treats each top-level entry with a "/" in it as a
        # directory item (including an explicit "weread/" entry), and each
        # top-level *.sh as a script.
        dirs, scripts = [], []
        for name in names:
            if "/" in name:
                top = name.split("/", 1)[0]
                if top not in dirs:
                    dirs.append(top)
            elif name.lower().endswith(".sh"):
                scripts.append(name)

        assert dirs, "PortMaster needs at least one top-level directory"
        assert scripts, "PortMaster needs at least one top-level .sh script"
        assert "weread" in dirs, "expected the weread/ directory"
        assert "Weread.sh" in scripts, "expected the Weread.sh launcher"
        assert "weread/port.json" in names, "expected weread/port.json"

        info = json.loads(zf.read("weread/port.json").decode("utf-8"))
        assert info["version"] == 2, info
        assert info["attr"]["title"], info
        assert zf.testzip() is None
    return names


def build(archive=None, browser=None, validate_after=True):
    """Write the package. browser=None produces the lightweight port."""
    archive = Path(archive or ARCHIVE)
    archive.parent.mkdir(parents=True, exist_ok=True)
    payload = verify_browser_payload(browser) if browser else None

    temporary = archive.with_suffix(".new.zip")
    written = []
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for source, arcname in entries():
            data = source.read_bytes()
            info = zipfile.ZipInfo(arcname)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | zip_mode(source, arcname)) << 16
            zf.writestr(info, data)
            written.append(arcname)
        if payload:
            for source in sorted(payload.rglob("*")):
                if not source.is_file():
                    continue
                arcname = "weread/browser/" + source.relative_to(payload).as_posix()
                info = zipfile.ZipInfo(arcname)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (stat.S_IFREG | zip_mode(source, arcname)) << 16
                zf.writestr(info, source.read_bytes())
                written.append(arcname)
        # PortMaster treats a directory entry as an item; add weread/ explicitly.
        dirinfo = zipfile.ZipInfo("weread/")
        dirinfo.external_attr = (stat.S_IFDIR | 0o755) << 16
        zf.writestr(dirinfo, b"")
        written.append("weread/")

    if validate_after:
        validate(temporary)

    payload_bytes = temporary.read_bytes()
    temporary.replace(archive)
    print("Verified %d entries, %d bytes: %s"
          % (len(written), len(payload_bytes), archive))
    print("sha256", hashlib.sha256(payload_bytes).hexdigest())
    return archive


def main(argv=None):
    """Build the release package, or the lite one when asked.

    A checkout without output/browser_payload (the common case: the payload is
    ~500MB and never committed) still gets a valid PortMaster package, just the
    lightweight one. That keeps the shape check in the unit tests runnable
    without downloading Chromium.
    """
    # Only look at argv when this file really is the program being run.
    # unittest imports it, and receiving unittest own "discover" argument
    # used to make the test run write a stray zip named "discover".
    argv = list(sys.argv[1:] if argv is None else argv) if __name__ == "__main__" else []
    if "--lite" in argv:
        return build(LITE_ARCHIVE, browser=None)
    target = Path(argv[0]) if argv else None
    if not DEFAULT_BROWSER_PAYLOAD.is_dir():
        print("note: no browser payload at %s -> building the lightweight package"
              % DEFAULT_BROWSER_PAYLOAD)
        return build(target or LITE_ARCHIVE, browser=None)
    return build(target, browser=DEFAULT_BROWSER_PAYLOAD)


if __name__ == "__main__":
    main()
