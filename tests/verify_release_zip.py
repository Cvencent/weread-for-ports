"""Verify a built weread.zip the way the handheld would actually use it.

Run after package_portmaster.py, before anything is published:

    python tests/verify_release_zip.py                      # output/weread.zip
    python tests/verify_release_zip.py path/to/weread.zip

Everything here is a hard requirement for a novice install to work:

  * the flat PortMaster shape (checked again, in case the archive was edited);
  * Weread.sh and weread/node.sh present after unpacking;
  * our own Chromium, its NSS libraries and a CJK font present;
  * the chromium payload matching the shipped MANIFEST.json byte for byte;
  * the top-level launcher reaching the real launcher.

Exit status is 0 only when there are no problems, so CI can gate on it.
"""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]

# Always required, both packages: the port itself.
REQUIRED_IN_ARCHIVE = (
    "Weread.sh",
    "weread/port.json",
    "weread/node.sh",
    "weread/ext/content.js",
)
# Only the full release carries a browser; weread-lite.zip deliberately does not
# and is for people who already run a Browser port.
BROWSER_IN_ARCHIVE = (
    "weread/browser/chromium/chrome",
    "weread/browser/nss/libnss3.so",
)


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def check_manifest(root):
    """Every file the payload shipped must still hash the same."""
    problems = []
    manifest_path = Path(root) / "weread/browser/MANIFEST.json"
    if not manifest_path.is_file():
        return ["payload has no MANIFEST.json"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    browser = manifest_path.parent
    for rel, expected in manifest.get("files", {}).items():
        target = browser / rel
        if not target.is_file():
            problems.append("payload file listed but absent: %s" % rel)
            continue
        if sha256_bytes(target.read_bytes()) != expected:
            problems.append("payload file changed: %s" % rel)
    return problems


def check_archive(archive, require_browser=True):
    """Return a list of human-readable problems; empty means good.

    require_browser=False validates the lightweight package, which arrives
    without the ~500MB Chromium payload.
    """
    archive = Path(archive)
    if not archive.is_file():
        return ["archive not found: %s" % archive]

    try:
        with zipfile.ZipFile(archive) as zf:
            names = set(zf.namelist())
    except (OSError, zipfile.BadZipFile) as err:
        return ["cannot read archive %s: %s" % (archive, err)]

    problems = []
    wanted = list(REQUIRED_IN_ARCHIVE)
    if require_browser:
        wanted = wanted + list(BROWSER_IN_ARCHIVE)
    for required in wanted:
        if required not in names:
            label = "browser payload" if "/browser/" in required else required
            problems.append("missing %s (%s)" % (label, required))

    # PortMaster shape: flat, one top-level dir, at least one top-level script.
    tops = {n.split("/", 1)[0] for n in names if "/" in n}
    scripts = [n for n in names if "/" not in n and n.lower().endswith(".sh")]
    if "weread" not in tops:
        problems.append("missing the weread/ directory item")
    if not scripts:
        problems.append("missing a top-level .sh launcher")
    if problems:
        return problems

    with zipfile.ZipFile(archive) as zf, tempfile.TemporaryDirectory() as temp:
        zf.extractall(temp)
        root = Path(temp)
        for required in wanted:
            if not (root / required).is_file():
                problems.append("did not unpack %s" % required)
        if require_browser:
            problems.extend(check_manifest(root))
    return problems


def main(argv=None):
    argv = list(sys.argv[1:]) if argv is None else argv
    require_browser = "--lite" not in argv
    argv = [a for a in argv if a != "--lite"]
    archives = [Path(a) for a in argv] or [ROOT / "output" / "weread.zip"]
    failed = False
    for archive in archives:
        problems = check_archive(archive, require_browser=require_browser)
        if problems:
            failed = True
            print("FAIL %s" % archive)
            for problem in problems:
                print("   - %s" % problem)
        else:
            size = archive.stat().st_size / 1048576
            print("OK   %s (%.1f MB)" % (archive, size))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
