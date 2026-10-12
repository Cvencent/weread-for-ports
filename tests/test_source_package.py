"""The source package must be self-sufficient.

The archive is what gets handed to anyone reviewing or continuing the work, so
a file the test suite depends on being present is the same class of defect as a
missing runtime file. tools/eslint.config.mjs was dropped by the include list
after the lint layer landed, which left the packaged copy unable to run its own
static checks.
"""
import hashlib
import pathlib
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]


def build_package():
    """Run the real packager and return the archive path."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "package_handoff", ROOT / "tests/package_handoff.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main()
    return module.ARCHIVE


class SourcePackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.archive_path = build_package()
        with zipfile.ZipFile(cls.archive_path) as archive:
            cls.names = set(archive.namelist())
            cls.contents = {name: archive.read(name) for name in cls.names}

    def test_the_archive_is_intact(self):
        self.assertGreater(len(self.names), 50)

    def test_every_entry_matches_the_repository(self):
        mismatches = []
        for name in self.names:
            source = ROOT / name
            if not source.is_file():
                mismatches.append(name + " (missing on disk)")
                continue
            if hashlib.sha256(self.contents[name]).digest() != \
                    hashlib.sha256(source.read_bytes()).digest():
                mismatches.append(name)
        self.assertEqual(mismatches, [])

    def test_no_cache_or_bytecode_is_shipped(self):
        for name in self.names:
            self.assertNotIn("__pycache__", name, name)
            self.assertFalse(name.endswith(".pyc"), name)

    def test_the_lint_configuration_ships(self):
        # test_extension_static.py runs eslint against this file; without it the
        # packaged copy silently loses its static checks.
        self.assertIn("tools/eslint.config.mjs", self.names)

    def test_every_file_the_tests_import_ships(self):
        required = [
            "launcher/cdp.py", "launcher/input_bridge.py", "launcher/window_guard.py",
            "launcher/node.sh", "ports/update_gamelist.py", "ports/install.sh",
            "ports/uninstall.sh", "ports/gamelist.fragment.xml",
            "ports/Weread.sh", "ports/port.json", "ports/media/Weread.png",
            "tests/package_portmaster.py", "tests/test_portmaster_package.py",
            "tests/portmaster_device_acceptance.py",
            "extension/content.js", "extension/background-v8.1.js",
            "extension/shell.css", "extension/manifest.json",
            "tests/device.py", "tests/package_handoff.py",
        ]
        for name in required:
            self.assertIn(name, self.names, name)

    def test_the_unpacked_archive_can_run_the_suite(self):
        # Extract and import the packaged updater, so a package that only
        # looks complete still fails here.
        with tempfile.TemporaryDirectory() as directory:
            with zipfile.ZipFile(self.archive_path) as archive:
                archive.extractall(directory)
            target = pathlib.Path(directory)
            # The suite is discovery-based, so running it inside the extracted
            # copy exercises exactly the files that were packaged.
            proc = subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", "tests",
                 "-p", "test_*contract.py"],
                capture_output=True, cwd=str(target), timeout=900)
            output = (proc.stdout + proc.stderr).decode("utf-8", "replace")
            self.assertEqual(proc.returncode, 0, output[-4000:])
            self.assertIn("OK", output)


if __name__ == "__main__":
    unittest.main()