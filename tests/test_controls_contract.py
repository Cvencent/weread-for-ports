import json
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
HANDOFF = pathlib.Path(r"D:\X35S\微信读书掌机版-交接包\源码")

class ControlsContractTests(unittest.TestCase):
    def test_extension_starts_before_first_page_paint_and_has_boot_mask(self):
        manifest = json.loads((ROOT / "extension/manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["content_scripts"][0]["run_at"], "document_start")
        css = (ROOT / "extension/shell.css").read_text(encoding="utf-8")
        self.assertIn("wr-hh-boot-mask", css)
        self.assertIn("wr-hh-boot-ready", css)

    def test_handheld_buttons_have_one_menu_and_scroll_mapping(self):
        for path in (ROOT / "launcher/weread.gptk", HANDOFF / "weread.gptk"):
            text = path.read_text(encoding="utf-8")
            self.assertRegex(text, r"(?m)^start\s*=\s*f10\s*$")
            self.assertRegex(text, r"(?m)^back\s*=\s*f9\s*$")
            self.assertRegex(text, r"(?m)^l2\s*=\s*home\s*$")
            self.assertRegex(text, r"(?m)^r2\s*=\s*end\s*$")
            self.assertNotRegex(text, r"(?m)^lefttrigger\s*=")
            self.assertNotRegex(text, r"(?m)^righttrigger\s*=")
            for key in ("up", "down", "left", "right"):
                self.assertEqual(len(re.findall(rf"(?m)^{key}\s*=", text)), 1)

    def test_launcher_clears_a_stale_input_bridge_before_start(self):
        text = (ROOT / "launcher/node.sh").read_text(encoding="utf-8")
        self.assertIn('pkill -f "$INPUT_BRIDGE" 2>/dev/null', text)
    def test_exit_combo_is_explicit(self):
        content = (ROOT / "extension/content.js").read_text(encoding="utf-8")
        self.assertIn("START + SELECT", content)

    def test_shell_menu_only_confirms_with_a(self):
        content = (ROOT / "extension/content.js").read_text(encoding="utf-8")
        self.assertIn("if (k === 'Enter') { runMenu();", content)
        self.assertNotIn("if (k === 'Enter' || k === ' ') { runMenu();", content)

if __name__ == "__main__": unittest.main()
