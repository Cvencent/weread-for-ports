"""isReader() must find the visible reader container, not only the first match.

isReader() decides between the reader and the browsing branch of the shell, and
navWanted(), candidates(), focusSweep() and the key handler all call it. It
used to test only the first element matching the reader selectors for
visibility, so a hidden stale container rendered ahead of the live one made the
shell treat a visible reader as a browsing page.
"""
import pathlib
import re
import shutil
import subprocess
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
HARNESS = pathlib.Path(__file__).resolve().parent / "_isreader_equivalence.js"


class IsReaderEquivalenceTests(unittest.TestCase):
    def test_visible_reader_beats_a_hidden_stale_container(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not available")
        result = subprocess.run([node, str(HARNESS)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("EQUIVALENCE: PASS", result.stdout)
        self.assertNotIn("BAD", result.stdout)

    def test_reader_check_scans_every_container(self):
        source = (ROOT / "extension/content.js").read_text(encoding="utf-8")
        body = re.search(r"function isReader\(\) \{(.*?)\n  \}", source, re.S).group(1)
        self.assertIn("$$('.wr_horizontalReader,.readerChapterContent_container')", body)
        self.assertIn("for (var i = 0; i < found.length; i++) if (shown(found[i])) return true;", body)
        self.assertNotIn("var reader = $('.wr_horizontalReader", body)

    def test_reader_route_still_wins_without_any_container(self):
        source = (ROOT / "extension/content.js").read_text(encoding="utf-8")
        body = re.search(r"function isReader\(\) \{(.*?)\n  \}", source, re.S).group(1)
        self.assertIn("if (/\\/web\\/reader\\//.test(location.pathname)) return true;", body)


if __name__ == "__main__":
    unittest.main()