"""move() must select exactly the same candidate after the refactor.

Every arrow keypress rebuilds the geometry of every candidate. move() used to
call rc() once directly and then absTop()/absLeft(), each of which reads the
rect again, doubling the layout reads per keypress. It now derives every
coordinate from a single measurement and replaces the same-row sort with a
running minimum. These tests prove the chosen index is unchanged.
"""
import pathlib
import re
import shutil
import subprocess
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
HARNESS = pathlib.Path(__file__).resolve().parent / "_move_equivalence.js"


class MoveEquivalenceTests(unittest.TestCase):
    def test_grid_movement_selects_the_same_candidate(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not available")
        result = subprocess.run([node, str(HARNESS)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("EQUIVALENCE: PASS", result.stdout)

    def test_movement_loop_reads_each_rect_once(self):
        source = (ROOT / "extension/content.js").read_text(encoding="utf-8")
        body = re.search(r"function move\(dir\) \{(.*?)\n    if \(best >= 0\)", source, re.S).group(1)
        # Coordinates come from the single `r = rc(...)` measurement.
        self.assertNotIn("absTop(t[i])", body)
        self.assertNotIn("absLeft(t[i])", body)
        self.assertIn("r.top + window.scrollY", body)
        self.assertIn("r.left + window.scrollX", body)
        # The same-row band is a running minimum instead of a sorted array.
        self.assertNotIn("band.push", body)
        self.assertIn("var bandBest = Infinity;", body)


if __name__ == "__main__":
    unittest.main()