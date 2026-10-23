"""install.sh and uninstall.sh must install and remove the same file set.

WeRead is one self-contained directory (ports/weread) plus a top-level Weread.sh
launcher and its icon, matching how every other port is laid out. uninstall.sh
must remove exactly that set and must never touch the borrowed Browser port
(Chromium/NSS) or the user's login profile.
"""
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class InstallSymmetryTests(unittest.TestCase):
    def setUp(self):
        self.install = (ROOT / "ports/install.sh").read_text(encoding="utf-8")
        self.uninstall = (ROOT / "ports/uninstall.sh").read_text(encoding="utf-8")

    def test_install_writes_one_self_contained_directory(self):
        # The launcher/helpers and the extension both land under ports/weread;
        # node.sh is named explicitly for its exec bit, the rest by loop.
        self.assertIn('mkdir -p "$WEREAD_DIR/ext" "$PORTS_DIR/media"', self.install)
        self.assertIn('cp "$ROOT/launcher/$file" "$WEREAD_DIR/$file"', self.install)
        self.assertIn('cp "$ROOT/extension/$file" "$WEREAD_DIR/ext/$file"', self.install)
        self.assertIn('"$WEREAD_DIR/node.sh"', self.install)
        self.assertIn('cp "$ROOT/ports/Weread.sh" "$PORTS_DIR/Weread.sh"', self.install)
        self.assertIn('cp "$ROOT/ports/media/Weread.png" "$PORTS_DIR/media/Weread.png"',
                      self.install)

    def test_install_no_longer_scatters_into_the_browser_or_config_dirs(self):
        # The old layout copied helpers into the shared Browser port and the
        # extension into ~/.config; the install path no longer mentions either.
        self.assertNotIn("WEREAD_EXT_DIR", self.install)
        self.assertNotIn('"$BROWSER_DIR/cdp.py"', self.install)
        self.assertNotIn('"$BROWSER_DIR/weread.gptk"', self.install)

    def test_install_ships_its_own_browser_instead_of_borrowing_one(self):
        # v1.3: a novice installs one thing. install.sh carries the bundled
        # Chromium payload into weread/browser/ just like weread.zip does.
        self.assertIn("BROWSER_SRC=", self.install)
        self.assertIn('"$WEREAD_DIR/browser"', self.install)

    def test_uninstall_removes_exactly_what_install_wrote(self):
        self.assertIn('rm -f "$PORTS_DIR/Weread.sh" "$PORTS_DIR/media/Weread.png"',
                      self.uninstall)
        self.assertIn('rm -rf "$WEREAD_DIR"', self.uninstall)

    def test_uninstall_keeps_the_browser_and_the_login_profile(self):
        # The only browser-dir files it may delete are the three legacy helpers.
        removed = set(re.findall(r'\$BROWSER_DIR/([^\s"\\]+)', self.uninstall))
        self.assertEqual(removed, {"cdp.py", "weread.gptk", "\u64cd\u4f5c\u8bf4\u660e.txt"})
        for keep in ("chromium", "chrome", "nss"):
            self.assertNotIn(keep, removed)
        self.assertIn("login profile were preserved", self.uninstall)
        self.assertNotIn("weread-profile", self.uninstall)

    def test_both_scripts_honour_the_same_environment_overrides(self):
        for name in ("PORTS_DIR", "WEREAD_BROWSER_DIR", "WEREAD_GAMELIST"):
            self.assertIn("${%s:-" % name, self.install)
            self.assertIn("${%s:-" % name, self.uninstall)

    def test_the_gamelist_entry_is_optional_and_symmetric(self):
        # WEREAD_GAMELIST defaults to 1 so the curated Chinese-named entry keeps
        # working; both scripts gate on it identically, so uninstall removes
        # exactly what install added. WEREAD_GAMELIST=0 is a pure drop-in.
        self.assertIn('if [ "${WEREAD_GAMELIST:-1}" = 1 ]; then', self.install)
        self.assertIn('if [ "${WEREAD_GAMELIST:-1}" = 1 ]; then', self.uninstall)
        self.assertIn("--fragment", self.install)
        self.assertIn("--remove", self.uninstall)


if __name__ == "__main__":
    unittest.main()
