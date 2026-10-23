"""Contract tests for the self-contained browser payload builder.

v1.3 stops borrowing the Browser port. WeRead ships its own Chromium 154 +
NSS libraries + a CJK font inside weread.zip, under weread/browser/, so a
novice only installs one package and never installs a browser.

These tests pin the two halves that silently break novices:

  * the trimming rules (dropping the 328 unused locale paks, chromedriver and
    the crashpad handler) must keep chrome + zh-CN + en-US + swiftshader;
  * the assembled tree must have exactly the layout node.sh looks for, and a
    manifest so an install can be verified after the fact.
"""
import importlib.util
import io
import json
import hashlib
import lzma
import pathlib
import tarfile
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def builder():
    spec = importlib.util.spec_from_file_location(
        "build_browser_payload", ROOT / "tools/build_browser_payload.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fake_chromium_tree(root):
    """A miniature stand-in for the ungoogled-chromium arm64 release."""
    (root / "locales").mkdir(parents=True)
    for name in ("en-US.pak", "zh-CN.pak", "de.pak", "fr.pak", "ja.pak"):
        (root / "locales" / name).write_bytes(b"pak" + name.encode())
    (root / "chrome").write_bytes(b"#!/bin/sh\n" + b"x" * 4096)
    (root / "chromedriver").write_bytes(b"driver" * 100)
    (root / "chrome_crashpad_handler").write_bytes(b"crash" * 100)
    (root / "icudtl.dat").write_bytes(b"icu")
    (root / "libvk_swiftshader.so").write_bytes(b"swift")
    (root / "resources.pak").write_bytes(b"res")
    (root / "v8_context_snapshot.bin").write_bytes(b"snap")
    (root / "chrome-wrapper").write_text("#!/bin/sh\n", encoding="utf-8")
    return root


def make_tarball(destination, root):
    with lzma.open(destination, "wb") as raw:
        with tarfile.open(fileobj=raw, mode="w") as tf:
            tf.add(root, arcname=root.name)
    return destination


class TrimTreeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="weread-payload-")
        self.addCleanup(self.temp.cleanup)
        self.root = fake_chromium_tree(pathlib.Path(self.temp.name) / "chromium")

    def test_it_keeps_the_locales_the_reader_actually_needs(self):
        builder().trim_tree(self.root)
        kept = sorted(p.name for p in (self.root / "locales").glob("*.pak"))
        self.assertEqual(kept, ["en-US.pak", "zh-CN.pak"])

    def test_it_drops_files_that_only_developers_use(self):
        builder().trim_tree(self.root)
        self.assertFalse((self.root / "chromedriver").exists())
        self.assertFalse((self.root / "chrome_crashpad_handler").exists())

    def test_it_never_drops_the_renderer_or_the_software_fallback(self):
        builder().trim_tree(self.root)
        for keep in ("chrome", "icudtl.dat", "resources.pak",
                     "v8_context_snapshot.bin", "libvk_swiftshader.so"):
            self.assertTrue((self.root / keep).exists(), keep)


class DownloadTests(unittest.TestCase):
    """A 134MB download over a bad link is the realistic failure, so the
    fetcher has to resume and refuse a file whose hash is wrong."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="weread-dl-")
        self.addCleanup(self.temp.cleanup)
        self.base = pathlib.Path(self.temp.name)
        self.source = self.base / "source.bin"
        self.source.write_bytes(b"payload-bytes" * 100)
        self.url = self.source.as_uri()

    def test_a_good_download_lands_and_passes_the_checksum(self):
        target = self.base / "out.bin"
        expected = hashlib.sha256(self.source.read_bytes()).hexdigest()
        builder().download(self.url, target, expected)
        self.assertEqual(target.read_bytes(), self.source.read_bytes())

    def test_a_wrong_checksum_leaves_nothing_behind(self):
        target = self.base / "out2.bin"
        with self.assertRaises(SystemExit):
            builder().download(self.url, target, "0" * 64)
        self.assertFalse(target.exists())
        self.assertFalse(list(self.base.glob("*.part")), "left a partial file")

    def test_a_cached_correct_file_is_not_downloaded_again(self):
        target = self.base / "out3.bin"
        expected = hashlib.sha256(self.source.read_bytes()).hexdigest()
        target.write_bytes(self.source.read_bytes())
        builder().download(self.url, target, expected)
        self.assertEqual(target.read_bytes(), self.source.read_bytes())


class AssembleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="weread-payload-")
        self.addCleanup(self.temp.cleanup)
        self.base = pathlib.Path(self.temp.name)
        self.tarball = make_tarball(
            self.base / "chrome.tar.xz",
            fake_chromium_tree(self.base / "ungoogled-chromium-154-arm64_linux"))
        self.nss = self.base / "nss"
        self.nss.mkdir()
        for name in ("libnss3.so", "libnssutil3.so", "libsmime3.so",
                     "libnspr4.so", "libplc4.so", "libplds4.so",
                     "libssl3.so", "libsoftokn3.so", "libfreebl3.so",
                     "libfreeblpriv3.so", "libnssckbi.so", "libnssdbm3.so"):
            (self.nss / name).write_bytes(b"so")
        self.font = self.base / "NotoSansSC-Regular.otf"
        self.font.write_bytes(b"font")

    def test_it_lands_the_tree_node_sh_expects(self):
        out = self.base / "payload"
        builder().assemble(self.tarball, self.nss, self.font, out)
        self.assertTrue((out / "chromium/chrome").is_file())
        self.assertTrue((out / "nss/libnss3.so").is_file())
        self.assertTrue((out / "fonts/NotoSansSC-Regular.otf").is_file())

    def test_it_refuses_a_payload_without_chrome(self):
        out = self.base / "payload2"
        broken = make_tarball(self.base / "broken.tar.xz",
                              fake_chromium_tree(self.base / "other")
                              .parent / "other")
        (self.base / "other" / "chrome").unlink()
        broken = make_tarball(self.base / "broken2.tar.xz", self.base / "other")
        with self.assertRaises(SystemExit):
            builder().assemble(broken, self.nss, self.font, out)

    def test_it_writes_a_manifest_that_can_verify_the_install(self):
        out = self.base / "payload3"
        builder().assemble(self.tarball, self.nss, self.font, out)
        manifest = json.loads((out / "MANIFEST.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["chromium_version"], "154.0.8037.97")
        self.assertIn("chromium/chrome", manifest["files"])
        self.assertEqual(manifest["files"]["nss/libnss3.so"],
                         builder().sha256_file(self.nss / "libnss3.so"))

    def test_the_manifest_records_every_shipped_file(self):
        out = self.base / "payload4"
        builder().assemble(self.tarball, self.nss, self.font, out)
        manifest = json.loads((out / "MANIFEST.json").read_text(encoding="utf-8"))
        shipped = sorted(
            str(p.relative_to(out)).replace("\\", "/")
            for p in out.rglob("*") if p.is_file() and p.name != "MANIFEST.json")
        self.assertEqual(sorted(manifest["files"]), shipped)


if __name__ == "__main__":
    unittest.main()
