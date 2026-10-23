"""node.sh must find its browser inside weread/, and say so when it cannot.

v1.3 stops borrowing the Browser port. The Chromium that used to live at
/storage/roms/ports/browser/chromium now ships inside weread/browser/, so the
launcher resolves it relative to itself. A novice who somehow ends up without
it must get a Chinese message they can act on, not a silent black screen.
"""
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
NODE = (ROOT / "launcher" / "node.sh").read_text(encoding="utf-8").replace("\r\n", "\n")


class SelfContainedBrowserTests(unittest.TestCase):
    def test_it_defaults_the_browser_to_the_copy_beside_the_launcher(self):
        self.assertIn('BROWSER_DIR="${WEREAD_BROWSER_DIR:-$HERE/browser}"', NODE)

    def test_it_still_honours_an_explicit_override(self):
        # Keeping the override means anyone already running a shared Browser
        # port (or a tester pointing at a different Chromium) is not broken.
        self.assertIn("WEREAD_BROWSER_DIR", NODE)

    def test_the_self_check_names_the_chromium_it_could_not_find(self):
        # The failure has to tell a novice which path was checked, otherwise
        # the only symptom is the app quitting back to the frontend.
        self.assertIn("$BROWSER_DIR/chromium/chrome", NODE)
        self.assertIn("weread.zip", NODE)

    def test_it_does_not_require_the_shared_browser_port_anymore(self):
        # Nothing may point at the sibling browser/ port by default.
        defaults = re.findall(r'\$\{WEREAD_BROWSER_DIR:-([^}]*)\}', NODE)
        self.assertTrue(defaults, "expected a WEREAD_BROWSER_DIR default")
        for default in defaults:
            self.assertNotIn("PORTS_DIR/browser", default)


class ExecutableBitTests(unittest.TestCase):
    """Python zipfile.extract does not restore unix permissions, and PortMaster
    only chmods when the ports live on ext4 (this handheld is exFAT). So an
    install can land a perfectly good chrome that is not yet +x. The launcher
    has to fix that itself instead of exiting."""

    def test_the_launcher_restores_the_executable_bit_before_using_chrome(self):
        self.assertIn("ensure_browser_exec", NODE)
        body = NODE.split("ensure_browser_exec()", 1)[1].split("\n}", 1)[0]
        self.assertIn("chmod", body)
        self.assertIn("chromium/chrome", body)

    def test_a_read_only_filesystem_does_not_break_startup(self):
        body = NODE.split("ensure_browser_exec()", 1)[1].split("\n}", 1)[0]
        self.assertIn("|| true", body)

    def test_it_runs_before_the_browser_is_used(self):
        self.assertLess(NODE.index("ensure_browser_exec"),
                        NODE.index('cd "$BROWSER_DIR/chromium"'))


class LauncherStillLoadsLibrariesTests(unittest.TestCase):
    def test_ld_library_path_uses_the_resolved_browser_dir(self):
        self.assertIn('export LD_LIBRARY_PATH="$BROWSER_DIR/nss:$BROWSER_DIR/chromium', NODE)

    def test_it_cds_into_the_resolved_chromium(self):
        self.assertIn('cd "$BROWSER_DIR/chromium"', NODE)


if __name__ == "__main__":
    unittest.main()
