"""pageBtn() must keep finding the same element after the lookup refactor.

The page turners are the most repeated lookup in the reader (Y / L1 / R1).
pageBtn used to run querySelectorAll("span,div,a,button") over the whole
document and read innerText on every hit, forcing a layout pass per keypress.
It now prunes with a widened tag set plus :empty and compares textContent.

The harness reads the selector straight out of content.js so the test cannot
drift away from the implementation.
"""
import pathlib
import re
import shutil
import subprocess
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
HARNESS = pathlib.Path(__file__).resolve().parent / "_pagebtn_equivalence.js"


class PageButtonEquivalenceTests(unittest.TestCase):
    def test_lookup_matches_the_original(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not available")
        result = subprocess.run([node, str(HARNESS)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("EQUIVALENCE: PASS", result.stdout)
        self.assertNotIn("BAD", result.stdout)

    def test_lookup_no_longer_scans_every_element(self):
        source = (ROOT / "extension/content.js").read_text(encoding="utf-8")
        body = re.search(r"function pageBtn\(dir\) \{(.*?)\n  \}", source, re.S).group(1)
        self.assertNotIn("querySelectorAll('span,div,a,button')", body)
        self.assertIn("var PAGE_LABEL_SEL =", source)
        self.assertIn(":empty", body)
        # textContent does not force layout; innerText does.
        self.assertIn("(e.textContent || '').trim()", body)
        self.assertNotIn("e.innerText", body)

    def test_original_tags_are_still_covered(self):
        source = (ROOT / "extension/content.js").read_text(encoding="utf-8")
        selector = re.search(r"var PAGE_LABEL_SEL =\s*'([^']+)'", source).group(1)
        tags = {tag.strip().lower() for tag in selector.split(",")}
        self.assertLessEqual({"span", "div", "a", "button"}, tags)


if __name__ == "__main__":
    unittest.main()
