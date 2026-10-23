"""The PortMaster package must stay installable without touching the device shell.

PortMaster does not run an install script: it unpacks the zip and the frontend
runs the top-level `.sh`. Two regressions are cheap to reintroduce and invisible
until a user tries to install, so they are pinned here:

  * the zip going back to a wrapped-directory shape, which check_port() rejects;
  * `set -e` creeping back into Weread.sh, which kills the launcher the moment
    PortMaster's control.txt probes for sudo on a device that has none.
"""
import importlib.util
import json
import pathlib
import shutil
import stat
import tempfile
import unittest
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]


def packager():
    spec = importlib.util.spec_from_file_location(
        "package_portmaster", ROOT / "tests/package_portmaster.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PortMasterPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pkg = packager()
        # Build into a scratch path. main() writes output/weread-lite.zip when
        # the browser payload is absent (a bare runner), and output/weread.zip
        # when it is present, so asking for an explicit path keeps the archive
        # location deterministic in both cases.
        scratch = pathlib.Path(tempfile.mkdtemp(prefix="weread-pkg-"))
        cls.addClassCleanup(shutil.rmtree, scratch, True)
        cls.archive = scratch / "weread.zip"
        cls.pkg.build(cls.archive, browser=None)
        with zipfile.ZipFile(cls.archive) as archive:
            cls.names = archive.namelist()
            cls.infos = {name: archive.getinfo(name) for name in cls.names}
            cls.port = json.loads(archive.read("weread/port.json").decode("utf-8"))

    def test_the_package_validates_the_way_portmaster_does(self):
        # Raises on any breach, so the assertion is simply that it returns.
        self.pkg.validate(self.archive)

    def test_the_zip_is_flat_with_a_launcher_and_a_directory(self):
        self.assertIn("Weread.sh", self.names)
        self.assertIn("weread/", self.names)
        self.assertNotIn("weread/Weread.sh", self.names)

    def test_nothing_escapes_the_ports_folder(self):
        for name in self.names:
            self.assertFalse(name.startswith("/"), name)
            self.assertNotIn("..", name.split("/"), name)

    def test_port_json_is_version_two_metadata(self):
        self.assertEqual(self.port["version"], 2)
        self.assertIn("weread/", self.port["items"])
        self.assertIn("Weread.sh", self.port["items"])
        attr = self.port["attr"]
        for key in ("title", "desc", "genres", "porter", "image"):
            self.assertTrue(attr[key], key)
        # The cover has to live inside the package or the frontend shows a blank
        # tile until somebody copies media/ by hand.
        self.assertEqual(attr["image"]["Weread.png"], "weread/Weread.png")
        self.assertIn("weread/Weread.png", self.names)

    def test_it_does_not_gate_itself_on_an_architecture(self):
        # harbourmaster.match_requirements() appends attr.arch to the device
        # requirement list and hides the port when the device does not match, so
        # a narrow arch value would hide WeRead from devices that could run it.
        # The port is shell + Python + JS and borrows whatever Chromium the
        # device already has, so it has no architecture of its own -- which is
        # also why every entry in the official catalogue ships [] here.
        self.assertEqual(self.port["attr"]["arch"], [])
        self.assertEqual(self.port["attr"]["reqs"], [])

    def test_the_launcher_and_helpers_stay_executable(self):
        for name in self.names:
            if not name.endswith((".sh", ".py")):
                continue
            mode = self.infos[name].external_attr >> 16
            self.assertTrue(mode & stat.S_IXUSR, name)

    def test_the_port_carries_no_login_state(self):
        # The profile belongs to the user on the device; shipping it would leak
        # one reader's session into everyone else's install.
        for name in self.names:
            self.assertNotIn("weread-profile", name)

    def test_the_first_launch_can_publish_cover_and_gamelist(self):
        for name in ("weread/update_gamelist.py", "weread/gamelist.fragment.xml"):
            self.assertIn(name, self.names)

    def test_the_launcher_looks_for_its_helpers_next_to_itself(self):
        # node.sh sits in weread/ inside the zip, so bootstrap_port() has to
        # read the cover, the gamelist updater and the fragment from weread/ too.
        # Pointing one level up only works in the old manual-install layout and
        # silently skips the gamelist entry on a real PortMaster install.
        launcher = (ROOT / "launcher/node.sh").read_text(encoding="utf-8")
        self.assertIn('COVER_SRC="$HERE/Weread.png"', launcher)
        self.assertIn('"$HERE/update_gamelist.py"', launcher)
        self.assertIn('"$HERE/gamelist.fragment.xml"', launcher)
        self.assertNotIn('"$HERE/../update_gamelist.py"', launcher)
        self.assertNotIn('"$HERE/../gamelist.fragment.xml"', launcher)
        self.assertNotIn('"$HERE/../Weread.png"', launcher)


class SshInstallParityTests(unittest.TestCase):
    """install.sh is the fallback, but it has to land the same tree.

    Two different trees would mean two code paths for the cover and the gamelist
    entry, and the SSH one would quietly stop bootstrapping the moment
    bootstrap_port() started reading them out of weread/.
    """

    def setUp(self):
        self.install = (ROOT / "ports" / "install.sh").read_text(encoding="utf-8")

    def test_it_ships_the_same_bootstrap_files_as_the_zip(self):
        pkg = packager()
        for source_rel, arcname in pkg.BOOTSTRAP_FILES:
            name = arcname.split("/", 1)[1]
            self.assertIn('cp "$ROOT/%s" "$WEREAD_DIR/%s"' % (source_rel, name),
                          self.install)
        # port.json lives in ports/ only; it still has to reach weread/ so the
        # tree is identical whether PortMaster or install.sh unpacked it.
        self.assertIn('cp "$ROOT/ports/port.json" "$WEREAD_DIR/port.json"', self.install)

    def test_extra_data_files_cannot_ship_world_writable(self):
        # A single find pass over weread/'s data files rather than a chmod per
        # name, so a file added to the package later cannot slip past at 777.
        self.assertIn("-maxdepth 1 -type f ! -name", self.install)
        self.assertIn("-exec chmod 644 {} +", self.install)

    def test_skipping_the_gamelist_still_gets_an_entry_on_first_launch(self):
        # WEREAD_GAMELIST=0 only defers the work; node.sh finishes it from the
        # copy inside weread/, so the flag stays a speed knob and not a feature
        # switch that silently drops the Chinese name and the cover.
        self.assertIn('if [ "${WEREAD_GAMELIST:-1}" = 1 ]; then', self.install)


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.script = (ROOT / "ports" / "Weread.sh").read_text(encoding="utf-8")

    def test_it_does_not_abort_on_controls_sudo_probe(self):
        # control.txt runs `sudo echo ...` to detect sudo; on a device without
        # sudo that returns 127, and `set -e` would exit before chrome starts.
        # Only executable lines count, so the comment naming the option is fine.
        directives = [line.strip() for line in self.script.splitlines()
                      if line.strip() and not line.strip().startswith("#")]
        for line in directives:
            self.assertNotRegex(line, r"^set\s+-[a-z]*e", line)
            self.assertNotRegex(line, r"^set\s+-[a-z]*u", line)

    def test_it_sources_portmaster_controls_the_way_other_ports_do(self):
        self.assertIn("controlfolder", self.script)
        self.assertIn("control.txt", self.script)
        self.assertIn("get_controls", self.script)

    def test_it_hands_over_to_the_launcher_next_to_it(self):
        self.assertIn('exec "$HERE/weread/node.sh"', self.script)

    def test_the_launcher_can_find_itself_from_any_working_directory(self):
        self.assertIn('cd "$(dirname "$0")"', self.script)


if __name__ == "__main__":
    unittest.main()
