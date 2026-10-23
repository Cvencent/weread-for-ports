"""A fresh device has no CJK font; the reader must not render tofu.

The old flow relied on someone having run a manual setup script that wrote
/storage/.config/fontconfig/fonts.conf and copied a font into /storage/.fonts.
The bundled Chromium now carries its own NotoSansSC, so the launcher has to
register that file with fontconfig itself - and must do it without clobbering
whatever the user or another port already configured.
"""
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
NODE = (ROOT / "launcher" / "node.sh").read_text(encoding="utf-8").replace("\r\n", "\n")


class CjkFontTests(unittest.TestCase):
    def test_the_launcher_registers_the_bundled_font_with_fontconfig(self):
        self.assertIn("fonts", NODE)
        self.assertIn("fontconfig", NODE)

    def test_it_writes_its_own_conf_d_file_instead_of_overwriting_theirs(self):
        # conf.d/ is included by fontconfig automatically, so dropping a file
        # there adds our font without destroying an existing fonts.conf.
        self.assertIn("/storage/.config/fontconfig/conf.d", NODE)
        self.assertNotIn("> /storage/.config/fontconfig/fonts.conf", NODE)

    def test_the_conf_points_at_the_font_that_ships_in_the_package(self):
        # The font lives in the browser payload, so the conf must reference the
        # resolved browser dir rather than a path someone typed by hand.
        self.assertIn('fonts_dir="$BROWSER_DIR/fonts"', NODE)
        self.assertIn("<dir>${fonts_dir}</dir>", NODE)

    def test_it_does_not_fail_the_launch_when_the_directory_is_read_only(self):
        # A device without a writable config dir must still start.
        setup = NODE.split("setup_cjk_font()", 1)
        self.assertEqual(len(setup), 2, "expected a setup_cjk_font function")
        body = setup[1].split("\n}", 1)[0]
        self.assertIn("|| true", body)


if __name__ == "__main__":
    unittest.main()