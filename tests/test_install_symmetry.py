"""install.sh and uninstall.sh must install and remove the same file set.

install.sh copies launcher files into two different directories (the Ports
launcher directory and the browser directory). uninstall.sh previously removed
only the first one, leaving the extension directory and the browser-directory
helpers behind. These contracts keep the two scripts in sync.
"""
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class InstallSymmetryTests(unittest.TestCase):
    def setUp(self):
        self.install = (ROOT / "ports/install.sh").read_text(encoding="utf-8")
        self.uninstall = (ROOT / "ports/uninstall.sh").read_text(encoding="utf-8")

    def browser_dir_targets(self, script):
        return set(re.findall(r'\$BROWSER_DIR/([^\s"\\]+)', script))

    def extension_files_installed(self):
        block = re.search(r"for file in ([^\n]*telemetry-rules\.json); do", self.install).group(1)
        return {name.strip() for name in block.split()}

    def test_uninstall_removes_every_file_install_puts_in_the_browser_dir(self):
        installed = self.browser_dir_targets(self.install)
        self.assertTrue(installed, "install.sh should reference the browser directory")
        removed = self.browser_dir_targets(self.uninstall)
        self.assertLessEqual(installed, removed,
                             "uninstall.sh leaves %s behind" % sorted(installed - removed))

    def test_uninstall_removes_the_extension_directory(self):
        self.assertIn('EXT_DIR="${WEREAD_EXT_DIR:-/storage/.config/weread-ext}"', self.uninstall)
        self.assertIn('rm -rf "$PORTS_DIR/weread" "$EXT_DIR"', self.uninstall)

    def test_uninstall_keeps_the_browser_and_the_login_profile(self):
        # Only the named helpers may be deleted from the browser directory.
        removed = self.browser_dir_targets(self.uninstall)
        self.assertNotIn("chromium", removed)
        self.assertNotIn("chrome", removed)
        self.assertNotIn("nss", removed)
        self.assertIn("profile and extracted browser files were preserved", self.uninstall)

    def test_both_scripts_honour_the_same_environment_overrides(self):
        for name in ("PORTS_DIR", "WEREAD_EXT_DIR", "WEREAD_BROWSER_DIR"):
            self.assertIn("${%s:-" % name, self.install)
            self.assertIn("${%s:-" % name, self.uninstall)

    def test_installed_paths_match_between_both_scripts(self):
        for path in ('"$PORTS_DIR/Weread.sh"', '"$PORTS_DIR/media/Weread.png"'):
            self.assertIn(path, self.install)
            self.assertIn(path, self.uninstall)
        self.assertIn('"$PORTS_DIR/weread"', self.install)
        self.assertIn('"$PORTS_DIR/weread"', self.uninstall)


if __name__ == "__main__":
    unittest.main()