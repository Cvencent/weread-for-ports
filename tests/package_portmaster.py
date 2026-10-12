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

Weread therefore ships:

  Weread.sh              top-level launcher -> extracted to the ports dir
  media/Weread.png       cover
  weread/                everything WeRead owns, self-contained
    port.json node.sh window_guard.py input_bridge.py cdp.py weread.gptk
    ext/content.js shell.css manifest.json background-v8.1.js telemetry-rules.json
    操作说明.txt

The result drops into PortMaster/autoinstall/ (confirm in the PortMaster UI) or
registers in the official catalogue so it appears in the PortMaster list.
"""
import hashlib
import json
from pathlib import Path
import stat
import zipfile


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "output" / "weread.zip"

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


def zip_mode(source):
    """Keep the executable bit on the scripts and helpers, data files 644."""
    if source.suffix in (".sh", ".py"):
        return 0o755
    return 0o644


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


def main():
    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    temporary = ARCHIVE.with_suffix(".new.zip")
    written = []
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for source, arcname in entries():
            data = source.read_bytes()
            info = zipfile.ZipInfo(arcname)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | zip_mode(source)) << 16
            zf.writestr(info, data)
            written.append(arcname)
        # PortMaster treats a directory entry as an item; add weread/ explicitly.
        dirinfo = zipfile.ZipInfo("weread/")
        dirinfo.external_attr = (stat.S_IFDIR | 0o755) << 16
        zf.writestr(dirinfo, b"")
        written.append("weread/")

    validate(temporary)

    payload = temporary.read_bytes()
    temporary.replace(ARCHIVE)
    print("Verified %d entries, %d bytes: %s" % (len(written), len(payload), ARCHIVE))
    print("sha256", hashlib.sha256(payload).hexdigest())
    for name in written:
        print("  ", name)


if __name__ == "__main__":
    main()
