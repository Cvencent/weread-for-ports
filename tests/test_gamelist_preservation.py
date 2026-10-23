"""Gamelist rewrites must not destroy anything the user wrote.

EmulationStation gamelists are hand-maintained: people group their libraries
with XML comments. ElementTree drops comments unless the parser is built with
insert_comments, so every install used to silently delete those comments from
the user's gamelist. Comments before the root element are not part of the
element tree at all, so they are carried through textually.

These tests run against the real updater, and the install/uninstall scripts are
exercised end to end so the shell layer is covered too.
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ports"))
from update_gamelist import remove_weread, upsert_weread  # noqa: E402


CURATED = b"""<?xml version="1.0"?>
<!-- curated by hand, do not regenerate -->
<gameList>
  <!-- action block -->
  <game>
    <path>./Zelda.sh</path>
    <name>Zelda</name>
    <image>./media/zelda.png</image>
  </game>
  <!-- end of action -->
</gameList>
"""


class GamelistPreservesUserContentTests(unittest.TestCase):
    def assertCommentsPreserved(self, source, result):
        self.assertEqual(result.count(b"<!--"), source.count(b"<!--"))

    def test_insert_keeps_every_comment(self):
        result = upsert_weread(CURATED)
        self.assertCommentsPreserved(CURATED, result)
        self.assertIn(b"<!-- curated by hand, do not regenerate -->", result)
        self.assertIn(b"<!-- action block -->", result)
        self.assertIn(b"<!-- end of action -->", result)

    def test_remove_keeps_every_comment(self):
        installed = upsert_weread(CURATED)
        self.assertCommentsPreserved(installed, remove_weread(installed))

    def test_comment_before_the_root_element_survives(self):
        # Not representable in the element tree, so it is copied through.
        source = b"<!-- head -->\n<gameList><game><path>./A.sh</path></game></gameList>"
        self.assertCommentsPreserved(source, upsert_weread(source))
        self.assertCommentsPreserved(source, remove_weread(source))

    def test_comment_positions_across_the_document(self):
        positions = {
            "before the root": b"<!-- head --><gameList><game><path>./A.sh</path></game></gameList>",
            "inside the list": b"<gameList><!-- mid --><game><path>./A.sh</path></game></gameList>",
            "inside a game": b"<gameList><game><!-- n --><path>./A.sh</path></game></gameList>",
            "after the last game": b"<gameList><game><path>./A.sh</path></game><!-- tail --></gameList>",
        }
        for name, source in positions.items():
            with self.subTest(name):
                self.assertCommentsPreserved(source, upsert_weread(source))
                self.assertCommentsPreserved(source, remove_weread(source))

    def test_other_games_are_untouched(self):
        result = upsert_weread(CURATED)
        root = ET.fromstring(result)
        names = [game.findtext("name") for game in root.findall("game")]
        self.assertEqual(names, ["Zelda", "微信读书"])

    def test_the_write_stays_idempotent(self):
        once = upsert_weread(CURATED)
        self.assertEqual(upsert_weread(once), once)
        self.assertEqual(upsert_weread(upsert_weread(once)), once)

    def test_the_entry_lands_after_the_last_game_not_before_a_comment(self):
        # A naive append would place the entry after a trailing "end of list"
        # comment, which reads as if the comment applies to the new entry.
        result = upsert_weread(CURATED).decode("utf-8")
        self.assertLess(result.index("Zelda"), result.index("微信读书"))
        self.assertLess(result.index("微信读书"), result.index("<!-- end of action -->"))


class InstallRoundTripTests(unittest.TestCase):
    """Run install.sh and uninstall.sh for real against a temporary tree."""

    def setUp(self):
        self.bash = self._git_bash()
        if not self.bash:
            self.skipTest("bash is not available")
        self.python = shutil.which("python") or shutil.which("python3")
        if not self.python:
            self.skipTest("python is not available")
        self.temp = tempfile.mkdtemp(prefix="weread-install-")
        self.addCleanup(shutil.rmtree, self.temp, ignore_errors=True)
        self.ports = Path(self.temp) / "ports"
        self.gamelist = self.ports / "gamelist.xml"
        self.ports.mkdir(parents=True)
        self.gamelist.write_bytes(CURATED)
        # install.sh now copies its own browser payload, so the fixture has to
        # look like one: a chrome stub plus one NSS library.
        chrome = self.ports / "browser" / "chromium" / "chrome"
        chrome.parent.mkdir(parents=True)
        chrome.write_text("#!/bin/sh\n", encoding="utf-8")
        chrome.chmod(0o755)
        nss = self.ports / "browser" / "nss" / "libnss3.so"
        nss.parent.mkdir(parents=True)
        nss.write_bytes(b"so")
        # Git Bash needs POSIX-style paths; the interpreter comes from the
        # tests' own environment, so ask python for a path Bash can use.
        self.mount = Path(self.bash).parent.parent
        self.ports_bash = self._to_posix(self.ports)
        self.python_bash = self._to_posix(Path(self.python))
        self.browser_bash = self._to_posix(self.ports / "browser")

    @staticmethod
    def _git_bash():
        for candidate in (r"C:\Program Files\Git\bin\bash.exe",
                          r"C:\Program Files\Git\usr\bin\bash.exe"):
            if Path(candidate).exists():
                return candidate
        return None

    @staticmethod
    def _to_posix(path):
        # C:\\Users\\x -> /c/Users/x, which is what Git Bash accepts.
        drive, rest = os.path.splitdrive(str(Path(path).resolve()))
        return "/" + drive[0].lower() + rest.replace("\\", "/")

    def _run(self, script):
        # install.sh calls `python3`, which does not exist on Windows, so a
        # shim forwards it to whichever interpreter the tests are running on.
        shim = Path(self.temp) / "shim"
        shim.mkdir(exist_ok=True)
        wrapper = shim / "python3"
        wrapper.write_text('#!/bin/sh\nexec "%s" "$@"\n' % self.python_bash, encoding="utf-8")
        wrapper.chmod(0o755)
        command = (
            "set -euo pipefail\n"
            'export PORTS_DIR="%s"\n'
            'export WEREAD_BROWSER_DIR="%s"\n'
            'cd "%s"\n'
            "bash ports/%s\n"
        ) % (self.ports_bash, self.browser_bash,
             self._to_posix(ROOT), script)
        # The shim goes on PATH through the environment rather than an export:
        # a Windows path in a shell PATH assignment gets split on its drive
        # colon, which silently hides the shim and lets the WindowsApps
        # python3 alias win instead.
        env = dict(os.environ)
        env["PATH"] = str(shim) + os.pathsep + env.get("PATH", "")
        proc = subprocess.run([self.bash, "-c", command],
                              capture_output=True, timeout=120, env=env)
        if proc.returncode:
            self.fail("%s failed: %s" % (script, proc.stderr.decode("utf-8", "replace")))
        return proc

    def test_install_then_uninstall_keeps_the_users_gamelist(self):
        self._run("install.sh")
        installed = self.gamelist.read_bytes()
        self.assertEqual(installed.count(b"<!--"), CURATED.count(b"<!--"))
        self.assertIn("微信读书", installed.decode("utf-8"))
        self.assertTrue((self.ports / "Weread.sh").exists())
        self.assertTrue((self.ports / "weread" / "ext" / "content.js").exists())
        self.assertTrue((self.ports / "weread" / "cdp.py").exists())

        # Running install twice must not accumulate entries or duplicates.
        self._run("install.sh")
        root = ET.fromstring(self.gamelist.read_bytes())
        weread = [game for game in root.findall("game")
                  if (game.findtext("path") or "").strip() in ("./Weread.sh", "Weread.sh")]
        self.assertEqual(len(weread), 1)

        self._run("uninstall.sh")
        remaining = self.gamelist.read_bytes()
        self.assertEqual(remaining.count(b"<!--"), CURATED.count(b"<!--"))
        self.assertNotIn("微信读书", remaining.decode("utf-8"))
        self.assertFalse((self.ports / "Weread.sh").exists())
        self.assertFalse((self.ports / "weread").exists())
        # The unrelated game and the browser itself must survive.
        self.assertIn("Zelda", remaining.decode("utf-8"))
        self.assertTrue((self.ports / "browser" / "chromium" / "chrome").exists())

    def test_install_is_safe_to_rerun_on_a_fresh_device(self):
        # A device with no gamelist at all must still get a valid one.
        self.gamelist.unlink()
        self._run("install.sh")
        root = ET.fromstring(self.gamelist.read_bytes())
        self.assertEqual(root.tag, "gameList")
        self.assertEqual(len(root.findall("game")), 1)


if __name__ == "__main__":
    unittest.main()