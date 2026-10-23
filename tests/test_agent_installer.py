"""install-agent.sh must be safe to hand to an AI agent or a novice.

The point of this script is that somebody can paste ONE command and end up with
a working WeRead, without understanding PortMaster, Chromium or the ports
layout. That makes the failure modes dangerous rather than merely annoying:

  * it must refuse to run as a partial install (no chrome, no launcher);
  * it must verify the download instead of trusting it;
  * it must never delete the user login profile, even on uninstall;
  * it must be non-interactive, because an agent cannot answer a prompt.
"""
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "ports" / "install-agent.sh"


class AgentInstallerContentTests(unittest.TestCase):
    def setUp(self):
        self.text = SCRIPT.read_text(encoding="utf-8").replace("\r\n", "\n")

    def test_the_script_exists_and_is_executable(self):
        self.assertTrue(SCRIPT.is_file())
        self.assertTrue(os.access(SCRIPT, os.X_OK))

    def test_it_is_non_interactive(self):
        # An agent or a scripted install cannot answer prompts.
        for banned in ("read -p", "read -r -p", "read -n"):
            self.assertNotIn(banned, self.text)

    def test_it_verifies_the_download_it_installs(self):
        self.assertIn("sha256sum", self.text)
        self.assertIn(".sha256", self.text)

    def test_it_never_touches_the_login_profile(self):
        # The profile is the one thing an update must preserve.
        self.assertNotIn("rm -rf \"$PROFILE\"", self.text)
        self.assertNotIn("rm -rf /storage/.config/weread-profile", self.text)
        self.assertIn("weread-profile", self.text)

    def test_it_checks_for_a_complete_install_before_declaring_success(self):
        self.assertIn("node.sh", self.text)
        self.assertIn("Weread.sh", self.text)
        self.assertIn("chromium/chrome", self.text)

    def test_it_explains_itself_in_chinese_for_novices(self):
        for phrase in ("\u5b89\u88c5\u5b8c\u6210", "\u5931\u8d25"):
            self.assertIn(phrase, self.text)

    def test_it_supports_uninstall_without_touching_the_browser_or_profile(self):
        self.assertIn("--uninstall", self.text)
        self.assertIn("WEREAD_GAMELIST", self.text)


class AgentInstallerRunTests(unittest.TestCase):
    """Run the real script against a fake device tree and a local zip."""

    def setUp(self):
        self.bash = next((c for c in (r"C:\Program Files\Git\bin\bash.exe",
                                      r"C:\Program Files\Git\usr\bin\bash.exe")
                          if pathlib.Path(c).exists()), None)
        if not self.bash:
            self.skipTest("bash is not available")
        self.temp = tempfile.mkdtemp(prefix="weread-agent-")
        self.addCleanup(shutil.rmtree, self.temp, ignore_errors=True)
        self.base = pathlib.Path(self.temp)
        self.ports = self.base / "ports"
        self.ports.mkdir(parents=True)
        self.profile = self.base / "weread-profile"
        self.profile.mkdir()
        (self.profile / "Cookies").write_text("keep me", encoding="utf-8")
        self.source_zip = self._make_source_zip()
        self.mount = pathlib.Path(self.bash).parent.parent

    def _to_posix(self, path):
        drive, rest = os.path.splitdrive(str(pathlib.Path(path).resolve()))
        return "/" + drive[0].lower() + rest.replace("\\", "/")

    def _make_source_zip(self):
        import zipfile
        archive = self.base / "weread-fake.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("Weread.sh", "#!/bin/sh\nexec \"$(dirname \"$0\")/weread/node.sh\"\n")
            zf.writestr("weread/node.sh", "#!/bin/sh\nexit 0\n")
            zf.writestr("weread/port.json", '{"version": 2, "attr": {"title": "x"}}')
            zf.writestr("weread/browser/chromium/chrome", "#!/bin/sh\n")
            zf.writestr("weread/browser/nss/libnss3.so", "so")
            zf.writestr("weread/ext/content.js", "js")
            zf.writestr("weread/Weread.png", b"png")
            zf.writestr("weread/update_gamelist.py", "print('x')\n")
            zf.writestr("weread/gamelist.fragment.xml", "<x/>\n")
        self.base.joinpath("weread-fake.zip")
        return archive

    def _env(self, archive=None):
        return {**os.environ,
                "WEREAD_PORTS_DIR": self._to_posix(self.ports),
                "WEREAD_PROFILE": self._to_posix(self.profile),
                "WEREAD_ARCHIVE": self._to_posix(archive or self.source_zip),
                "WEREAD_GAMELIST": "0"}

    def _run(self, *args, archive=None):
        # Pass argv directly instead of going through a shell: the Windows
        # command interpreter mangles the quotes a -lc string would need.
        return subprocess.run([self.bash, self._to_posix(SCRIPT), *args],
                              capture_output=True, text=True,
                              encoding="utf-8", errors="replace",
                              env=self._env(archive))

    def test_installing_from_a_local_archive_lands_the_port(self):
        result = self._run("--from-file")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.ports / "Weread.sh").is_file())
        self.assertTrue((self.ports / "weread" / "node.sh").is_file())
        self.assertTrue((self.ports / "weread" / "browser" / "chromium" / "chrome").is_file())

    def test_installing_keeps_the_login_profile(self):
        self._run("--from-file")
        self.assertTrue((self.profile / "Cookies").is_file())
        self.assertEqual((self.profile / "Cookies").read_text(encoding="utf-8"),
                         "keep me")

    def test_uninstalling_removes_the_port_but_keeps_the_profile(self):
        self._run("--from-file")
        result = self._run("--uninstall")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.ports / "Weread.sh").exists())
        self.assertFalse((self.ports / "weread").exists())
        self.assertTrue((self.profile / "Cookies").is_file())

    def test_it_fails_loudly_when_the_archive_has_no_browser(self):
        import zipfile
        broken = self.base / "weread-broken.zip"
        with zipfile.ZipFile(broken, "w") as zf:
            zf.writestr("Weread.sh", "#!/bin/sh\n")
            zf.writestr("weread/node.sh", "#!/bin/sh\n")
        result = self._run("--from-file", archive=broken)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.ports / "weread" / "browser").exists())


if __name__ == "__main__":
    unittest.main()
