"""The released weread.zip must contain its own browser.

A novice cannot be asked to install the Browser port first. So the shipped
package carries the whole Chromium payload under weread/browser/, and this
suite pins the consequences that are easy to get wrong:

  * the payload is optional for developers (a source-only zip still builds);
  * once included it is complete - chrome, the NSS libraries and a CJK font;
  * the extra weight never lands in the repo or in the source package;
  * zips stay stream-safe for PortMaster's extractor (no symlinks, no
    absolute paths, no traversal).
"""
import importlib.util
import pathlib
import unittest
import zipfile


ROOT = pathlib.Path(__file__).resolve().parents[1]


def packager():
    spec = importlib.util.spec_from_file_location(
        "package_portmaster", ROOT / "tests/package_portmaster.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_browser_tree(root):
    (root / "chromium" / "locales").mkdir(parents=True)
    (root / "chromium" / "chrome").write_bytes(b"#!/bin/sh\n")
    (root / "chromium" / "icudtl.dat").write_bytes(b"icu")
    (root / "chromium" / "locales" / "zh-CN.pak").write_bytes(b"zh")
    (root / "nss").mkdir()
    (root / "nss" / "libnss3.so").write_bytes(b"so")
    (root / "fonts").mkdir()
    (root / "fonts" / "NotoSansSC-Regular.otf").write_bytes(b"font")
    (root / "MANIFEST.json").write_text('{"chromium_version": "154.0.8037.97"}',
                                        encoding="utf-8")
    return root


class FullBundleTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.temp = tempfile.TemporaryDirectory(prefix="weread-full-")
        self.addCleanup(self.temp.cleanup)
        self.payload = make_browser_tree(pathlib.Path(self.temp.name) / "browser_payload")

    def build(self, **kwargs):
        pkg = packager()
        archive = pathlib.Path(self.temp.name) / (kwargs.pop("name", "full.zip"))
        pkg.build(archive, **kwargs)
        return archive

    def test_the_source_only_zip_still_builds_without_a_payload(self):
        archive = self.build(name="lite.zip")
        with zipfile.ZipFile(archive) as zf:
            names = zf.namelist()
        self.assertIn("weread/node.sh", names)
        self.assertNotIn("weread/browser/chromium/chrome", names)

    def test_the_full_zip_carries_the_whole_browser(self):
        archive = self.build(browser=self.payload)
        with zipfile.ZipFile(archive) as zf:
            names = set(zf.namelist())
        for required in ("weread/browser/chromium/chrome",
                         "weread/browser/nss/libnss3.so",
                         "weread/browser/fonts/NotoSansSC-Regular.otf",
                         "weread/browser/MANIFEST.json"):
            self.assertIn(required, names)

    def test_the_full_zip_is_flat_and_has_no_symlinks_or_traversal(self):
        archive = self.build(browser=self.payload)
        with zipfile.ZipFile(archive) as zf:
            for info in zf.infolist():
                self.assertFalse(info.filename.startswith("/"), info.filename)
                self.assertNotIn("..", info.filename.split("/"), info.filename)
                # 0xA000 is the Unix symlink bit in the high 16 bits.
                mode = info.external_attr >> 16
                self.assertNotEqual(mode & 0xF000, 0xA000, info.filename)

    def test_chrome_keeps_its_executable_bit_in_the_zip(self):
        archive = self.build(browser=self.payload)
        with zipfile.ZipFile(archive) as zf:
            info = zf.getinfo("weread/browser/chromium/chrome")
        self.assertTrue((info.external_attr >> 16) & 0o111, "chrome must be executable")

    def test_a_payload_missing_chrome_fails_the_build(self):
        (self.payload / "chromium" / "chrome").unlink()
        with self.assertRaises(SystemExit):
            self.build(browser=self.payload)

    def test_the_manifest_is_carried_so_an_install_can_be_verified(self):
        archive = self.build(browser=self.payload)
        with zipfile.ZipFile(archive) as zf:
            self.assertIn("154.0.8037.97",
                          zf.read("weread/browser/MANIFEST.json").decode("utf-8"))


class RepoHygieneTests(unittest.TestCase):
    def test_the_browser_payload_is_never_committed(self):
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("output/", ignore)

    def test_the_source_package_has_no_browser_binaries(self):
        from test_source_package import build_package
        with zipfile.ZipFile(build_package()) as archive:
            names = archive.namelist()
        offenders = [n for n in names if "browser/chromium" in n]
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
