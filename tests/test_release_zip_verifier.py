"""A release zip has to be provably loadable before it is published.

Verifying the zip's shape (as package_portmaster.validate does) only proves
PortMaster will unpack it. This verifier goes further: it unpacks the real
archive into a scratch ports tree, runs the same checks the launcher runs at
startup, and proves the payload is byte-identical to the manifest that was
shipped alongside it.
"""
import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def verifier():
    spec = importlib.util.spec_from_file_location(
        "verify_release_zip", ROOT / "tests/verify_release_zip.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class VerifierUnitTests(unittest.TestCase):
    def test_it_reports_a_missing_archive_instead_of_crashing(self):
        v = verifier()
        problems = v.check_archive(ROOT / "no-such-archive.zip")
        self.assertTrue(problems)
        self.assertTrue(any("not found" in p for p in problems))

    def test_it_rejects_a_zip_without_the_browser_payload(self):
        import tempfile
        import zipfile
        with tempfile.TemporaryDirectory() as temp:
            archive = pathlib.Path(temp) / "lite.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("Weread.sh", "#!/bin/sh\n")
                zf.writestr("weread/node.sh", "#!/bin/sh\n")
                zf.writestr("weread/ext/content.js", "js")
            problems = verifier().check_archive(archive)
        self.assertTrue(any("browser" in p for p in problems), problems)


class LiteModeTests(unittest.TestCase):
    """The lightweight package is a supported download for people who already
    run a Browser port, so the verifier must be able to check it too."""

    def setUp(self):
        import tempfile
        import zipfile
        self.temp = tempfile.TemporaryDirectory(prefix="weread-lite-")
        self.addCleanup(self.temp.cleanup)
        self.archive = pathlib.Path(self.temp.name) / "lite.zip"
        with zipfile.ZipFile(self.archive, "w") as zf:
            zf.writestr("Weread.sh", "#!/bin/sh\n")
            zf.writestr("weread/node.sh", "#!/bin/sh\n")
            zf.writestr("weread/ext/content.js", "js")
            zf.writestr("weread/port.json", '{"version": 2, "attr": {"title": "x"}}')

    def test_strict_mode_requires_the_browser(self):
        problems = verifier().check_archive(self.archive)
        self.assertTrue(any("browser" in p for p in problems), problems)

    def test_lite_mode_accepts_a_package_without_the_browser(self):
        problems = verifier().check_archive(self.archive, require_browser=False)
        self.assertEqual(problems, [])

    def test_lite_mode_still_requires_the_real_launcher(self):
        import zipfile
        broken = pathlib.Path(self.temp.name) / "broken.zip"
        with zipfile.ZipFile(broken, "w") as zf:
            zf.writestr("Weread.sh", "#!/bin/sh\n")
        problems = verifier().check_archive(broken, require_browser=False)
        self.assertTrue(problems)


if __name__ == "__main__":
    unittest.main()
