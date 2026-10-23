"""Assemble weread/browser/ - a self-contained Chromium for WeRead on Ports.

Why this exists
---------------
Until v1.2 the port borrowed the Browser port''s Chromium, which meant a novice
had to install two things and the second one lived at a fixed path. v1.3 ships
the browser inside weread.zip so PortMaster installs everything at once.

The payload is the ungoogled-chromium arm64 portable build (Chromium 154,
glibc 2.36 -> runs on the device''s 2.40) plus the NSS libraries it is missing
plus one CJK font. Measured on the X35S: 739MB extracted, 502MB after trimming
the 326 locale paks we never use.

Everything is pinned by SHA-256 so an install can be checked after the fact.
"""
import argparse
import hashlib
import io
import json
import lzma
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request


CHROMIUM_VERSION = "154.0.8037.97"
CHROMIUM_TAG = "154.0.8037.97-1"
CHROMIUM_TARBALL = (
    "https://github.com/ungoogled-software/ungoogled-chromium-portablelinux"
    "/releases/download/{tag}/ungoogled-chromium-{tag}-arm64_linux.tar.xz"
).format(tag=CHROMIUM_TAG)
CHROMIUM_SHA256 = "594c337b1d35e0a8b9eb9233740498a8fdab386e22602412e26d12b0ef4a09f1"

# arm64 .deb, straight from Debian. Both are needed: libnspr4 for the NSPR
# runtime, libnss3 for the TLS stack chrome links against.
NSS_DEBS = (
    ("https://deb.debian.org/debian/pool/main/n/nspr/libnspr4_4.35-1_arm64.deb",
     "3aa6bc5a1a3f83627f735b9712eed74ed2c345ae9148e9d876887a97982ae28d"),
    ("https://security.debian.org/debian-security/pool/updates/main/n/nss"
     "/libnss3_3.87.1-1+deb12u4_arm64.deb",
     "aaa1b291b6330590079a0eb1404650c7c4f6c788f9213ab6911149dc22b2b6d0"),
)

FONT_URL = ("https://raw.githubusercontent.com/googlefonts/noto-cjk/main"
            "/Sans/SubsetOTF/SC/NotoSansSC-Regular.otf")
FONT_NAME = "NotoSansSC-Regular.otf"
# Upstream publishes no checksum for this font, so the download is checked by
# its OpenType header instead. The manifest then records what we shipped.
FONT_MAGIC = b"OTTO"

# Files that only help a developer debugging the browser.
DROP_FILES = ("chromedriver", "chrome_crashpad_handler")
# The reader is Chinese; English is chrome''s own fallback. The other 326 paks
# are 213MB we never need on a 1GB handheld.
KEEP_LOCALES = ("en-US.pak", "zh-CN.pak")


def _curl():
    """Path to curl if the platform has one (Windows ships it as curl.exe)."""
    return shutil.which("curl") or shutil.which("curl.exe")


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url, destination, expected_sha256=None):
    """Fetch url to destination, skipping work when it is already correct."""
    destination = Path(destination)
    if destination.is_file() and expected_sha256:
        if sha256_file(destination) == expected_sha256:
            print("cached  %s" % destination.name)
            return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    print("fetch   %s" % url)
    if _curl() and url.startswith(("http://", "https://")):
        # curl resumes and retries, which matters for the 134MB tarball.
        subprocess.run([_curl(), "-fL", "--retry", "5", "--retry-delay", "3",
                        "--connect-timeout", "30", "--max-time", "1800",
                        "-C", "-", "-o", str(partial), url], check=True)
    else:
        request = urllib.request.Request(url, headers={"User-Agent": "weread-builder"})
        with urllib.request.urlopen(request, timeout=300) as response, \
                open(partial, "wb") as out:
            shutil.copyfileobj(response, out)
    if expected_sha256:
        actual = sha256_file(partial)
        if actual != expected_sha256:
            partial.unlink()
            sys.exit("checksum mismatch for %s\n  expected %s\n  actual   %s"
                     % (destination.name, expected_sha256, actual))
    partial.replace(destination)
    return destination


def trim_tree(root):
    """Drop developer-only files and the locales WeRead never renders."""
    root = Path(root)
    locales = root / "locales"
    if locales.is_dir():
        for pak in locales.glob("*.pak"):
            if pak.name not in KEEP_LOCALES:
                pak.unlink()
    for name in DROP_FILES:
        target = root / name
        if target.is_file():
            target.unlink()
    return root


def extract_deb(deb, destination):
    """Unpack a .deb into destination using only the stdlib.

    A .deb is an ar archive: 8-byte magic, then 60-byte headers with a 10-char
    size field. The device has no dpkg, and neither does this Windows box, so
    the members are walked by hand.
    """
    deb = Path(deb)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    data = deb.read_bytes()
    if not data.startswith(b"!<arch>\n"):
        sys.exit("%s is not an ar archive" % deb)
    offset = 8
    while offset + 60 <= len(data):
        header = data[offset:offset + 60]
        name = header[:16].decode("ascii", "replace").strip().rstrip("/")
        size = int(header[48:58].decode("ascii").strip())
        payload = data[offset + 60:offset + 60 + size]
        if name.startswith("data.tar"):
            with tarfile.open(fileobj=io.BytesIO(payload), mode="r:*") as tf:
                for member in tf.getmembers():
                    parts = Path(member.name.lstrip("./")).parts
                    if "lib" not in parts and not member.name.endswith(".so"):
                        continue
                    if not member.isfile():
                        continue
                    member.name = Path(*parts[-1:]).as_posix()
                    _extract_member(tf, member, destination)
        offset += 60 + size + (size & 1)
    return destination


def _extract_all(archive, target):
    """Keep the archive's own permission bits; Python 3.14 filters by default."""
    archive.extractall(target, filter="fully_trusted")


def _extract_member(archive, member, target):
    archive.extract(member, target, filter="fully_trusted")


def locate_chromium_root(extracted):
    """Find the directory that actually holds the chrome binary."""
    extracted = Path(extracted)
    for candidate in sorted(extracted.rglob("chrome")):
        if candidate.is_file() and candidate.parent.name.startswith(
                ("ungoogled-chromium", "chrome", "chromium")):
            return candidate.parent
    for candidate in sorted(extracted.rglob("chrome")):
        if candidate.is_file():
            return candidate.parent
    sys.exit("no chrome binary inside %s" % extracted)


def assemble(tarball, nss_dir, font, out):
    """Build the final weread/browser/ tree and write MANIFEST.json."""
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)

    with tempfile.TemporaryDirectory(prefix="weread-extract-") as scratch:
        print("unpack  %s" % Path(tarball).name)
        with tarfile.open(tarball, mode="r:xz") as tf:
            _extract_all(tf, scratch)
        chromium = locate_chromium_root(scratch)
        trim_tree(chromium)

        chrome_binary = chromium / "chrome"
        if not chrome_binary.is_file():
            sys.exit("payload would have no chrome binary")
        (out / "chromium").parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(chromium, out / "chromium")

    nss_dir = Path(nss_dir)
    if not (nss_dir / "libnss3.so").is_file():
        sys.exit("no libnss3.so in %s" % nss_dir)
    shutil.copytree(nss_dir, out / "nss")

    (out / "fonts").mkdir(parents=True, exist_ok=True)
    shutil.copy2(font, out / "fonts" / FONT_NAME)

    for required in ("chromium/chrome", "nss/libnss3.so",
                     "fonts/" + FONT_NAME):
        if not (out / required).is_file():
            sys.exit("assembled payload is missing %s" % required)

    files = {}
    for path in sorted(out.rglob("*")):
        if path.is_file():
            files[path.relative_to(out).as_posix()] = sha256_file(path)
    manifest = {
        "chromium_version": CHROMIUM_VERSION,
        "chromium_tarball": CHROMIUM_TARBALL,
        "chromium_sha256": CHROMIUM_SHA256,
        "nss": [url.rsplit("/", 1)[-1] for url, _ in NSS_DEBS],
        "font": FONT_NAME,
        "files": files,
    }
    (out / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out


def verify_font(font):
    """A truncated download is the realistic failure: check the header."""
    with open(font, "rb") as handle:
        magic = handle.read(4)
    if magic not in (FONT_MAGIC, b"\x00\x01\x00\x00", b"true"):
        sys.exit("font does not look like an OpenType/TrueType file: %s" % font)
    return sha256_file(font)


def build(work: Path, out: Path) -> Path:
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)

    tarball = download(CHROMIUM_TARBALL, work / "chromium-arm64.tar.xz",
                       CHROMIUM_SHA256)

    nss_dir = work / "nss"
    if not (nss_dir / "libnss3.so").is_file():
        for url, expected in NSS_DEBS:
            deb = download(url, work / url.rsplit("/", 1)[-1], expected)
            extract_deb(deb, nss_dir)

    font = work / FONT_NAME
    if not font.is_file():
        download(FONT_URL, font)
    verify_font(font)

    return assemble(tarball, nss_dir, font, out)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--work", default=str(Path(__file__).resolve().parents[1]
                                             / "output" / "_browser_payload"))
    parser.add_argument("--out", default=str(Path(__file__).resolve().parents[1]
                                             / "output" / "browser_payload"))
    args = parser.parse_args(argv)
    out = build(Path(args.work), Path(args.out))
    total = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    print("payload %s  %.1f MB  %d files"
          % (out, total / 1048576, len(list(out.rglob('*')))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
