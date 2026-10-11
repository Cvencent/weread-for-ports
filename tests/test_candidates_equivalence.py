"""The candidates() filter and tab merge must stay behavior-identical.

candidates() is the hottest function in the shell: every navigation key and
every focus sweep rebuilds this list. It was optimised to take one layout
read per candidate and to merge nav tabs through a Set instead of repeated
indexOf scans. These tests pin the observable result of that refactor.
"""
import pathlib
import re
import shutil
import subprocess
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
HARNESS = pathlib.Path(__file__).resolve().parent / "_candidates_equivalence.js"


class CandidatesEquivalenceTests(unittest.TestCase):
    def test_filter_and_tab_merge_match_the_original(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not available")
        result = subprocess.run([node, str(HARNESS)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("EQUIVALENCE: PASS", result.stdout)
        self.assertNotIn("BAD", result.stdout)

    def test_candidate_filter_reads_layout_once_per_element(self):
        source = (ROOT / "extension/content.js").read_text(encoding="utf-8")
        body = re.search(r"function candidates\(\) \{(.*?)\n    cache = out;", source, re.S).group(1)
        # One rect read feeds both the size test and the oversized-container test.
        self.assertIn("if (!e.isConnected) continue;", body)
        self.assertIn("var r = rc(e);", body)
        self.assertIn("if (r.width < 18 || r.height < 14) continue;", body)
        self.assertIn("if (!shownSized(e, r)) continue;", body)
        self.assertNotIn("if (!shown(e)) continue;", body)

    def test_nav_tabs_are_merged_with_a_set(self):
        source = (ROOT / "extension/content.js").read_text(encoding="utf-8")
        body = re.search(r"function candidates\(\) \{(.*?)\n    cache = out;", source, re.S).group(1)
        self.assertIn("var inOut = new Set(out);", body)
        self.assertIn("var tabSet = new Set(tabs);", body)
        self.assertNotIn("out.indexOf(tabs[k])", body)
        self.assertNotIn("tabs.indexOf(out[m])", body)


if __name__ == "__main__":
    unittest.main()