"""Every consumed key must also stop propagation.

The shell's keydown listener runs in the capture phase. Where it handles a key
it calls preventDefault, and every other branch in that handler also calls
stopPropagation so the site never sees the same keydown. The three scroll keys
(space, PageUp, PageDown) were missing it, which let the site's own handlers
react to the same press.
"""
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "extension/content.js").read_text(encoding="utf-8")

HANDLER = re.search(
    r"document\.addEventListener\('keydown', function \(e\) \{(.*?)\n  \}, true\);",
    SOURCE, re.S).group(1)


class ConsumedKeyPropagationTests(unittest.TestCase):
    def branches(self):
        # Every `... e.preventDefault(); ...; return;` arm inside the handler.
        return re.findall(r"e\.preventDefault\(\);(?P<rest>[^;]*); return;", HANDLER)

    def test_no_consumed_key_leaks_to_the_site(self):
        leaks = [rest for rest in self.branches() if "stopPropagation" not in rest]
        self.assertEqual(leaks, [],
                         "these keydown arms preventDefault without stopPropagation: %s" % leaks)

    def test_scroll_keys_are_covered(self):
        scroll_arms = [line for line in HANDLER.splitlines() if "window.scrollBy" in line]
        self.assertEqual(len(scroll_arms), 3, scroll_arms)
        for line in scroll_arms:
            self.assertIn("e.preventDefault(); e.stopPropagation(); return;", line)

    def test_handler_still_handles_the_expected_keys(self):
        # Guard against a refactor that makes the assertion above vacuous.
        self.assertGreater(len(self.branches()), 20)
        for key in ("'Enter'", "'Escape'", "'F10'", "'Tab'", "'F9'", "'Home'", "'End'"):
            self.assertIn(key, HANDLER, key)


if __name__ == "__main__":
    unittest.main()
