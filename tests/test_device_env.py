"""The local credential file must stay local.

`.device.env` holds a real handheld password, so it is git-ignored and outside
the source-package allowlist. These tests pin both halves of that promise plus
the parsing that makes the file usable without exporting variables first.
"""
import os
import pathlib
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
try:
    import device
except ImportError as err:  # paramiko is only needed for the handheld
    device = None
    _DEVICE_IMPORT_ERROR = err
else:
    _DEVICE_IMPORT_ERROR = None
from test_source_package import build_package


ROOT = pathlib.Path(__file__).resolve().parents[1]


class LocalEnvTests(unittest.TestCase):
    def setUp(self):
        if device is None:
            self.skipTest("device helpers unavailable: %s" % _DEVICE_IMPORT_ERROR)

    def write(self, text):
        handle = tempfile.NamedTemporaryFile("w", suffix=".env", delete=False,
                                             encoding="utf-8", newline="\n")
        handle.write(text)
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        return handle.name

    def test_it_reads_weread_keys_and_skips_the_rest(self):
        path = self.write(
            "# local only\n"
            "\n"
            "WEREAD_HOST=10.0.0.9\n"
            "WEREAD_PASSWORD='secret'\n"
            "WEREAD_USER=root\n"
            "PATH_NOT_WEREAD=nope\n"
            "garbage line without equals\n")
        self.assertEqual(device.load_local_env(path), {
            "WEREAD_HOST": "10.0.0.9",
            "WEREAD_PASSWORD": "secret",
            "WEREAD_USER": "root",
        })

    def test_a_missing_file_is_not_an_error(self):
        self.assertEqual(device.load_local_env(ROOT / "no-such-device.env"), {})

    def test_the_parsed_values_are_usable_as_settings(self):
        path = self.write("WEREAD_HOST=10.0.0.9\nWEREAD_PASSWORD=secret\n")
        self.assertEqual(device.load_local_env(path), {
            "WEREAD_HOST": "10.0.0.9", "WEREAD_PASSWORD": "secret"})

    def test_settings_survive_a_cleared_environment(self):
        # This suite runs next to the real-hardware tests, so anything that
        # drops WEREAD_* from os.environ must not switch the device off.
        saved = {key: os.environ.pop(key, None)
                 for key in ("WEREAD_HOST", "WEREAD_PASSWORD")}
        self.addCleanup(self.restore, saved)
        if not device.LOCAL:
            self.skipTest("no local .device.env in this checkout")
        self.assertEqual(device.setting("WEREAD_HOST"), device.LOCAL["WEREAD_HOST"])
        self.assertFalse(device.missing_credentials())

    def test_a_real_environment_variable_still_wins(self):
        previous = os.environ.get("WEREAD_HOST")
        os.environ["WEREAD_HOST"] = "from-shell"
        self.addCleanup(self.restore, {"WEREAD_HOST": previous})
        self.assertEqual(device.setting("WEREAD_HOST"), "from-shell")

    def restore(self, saved):
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_empty_values_do_not_configure_a_device(self):
        path = self.write("WEREAD_HOST=\nWEREAD_PASSWORD=   \n")
        self.assertEqual(device.load_local_env(path), {})


class ArchiveHygieneTests(unittest.TestCase):
    def test_the_credential_file_never_ships(self):
        with zipfile.ZipFile(build_package()) as archive:
            names = archive.namelist()
        self.assertNotIn(".device.env", names)
        self.assertFalse([name for name in names if name.endswith(".env")], names)


if __name__ == "__main__":
    unittest.main()
