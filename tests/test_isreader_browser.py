"""isReader() must find the visible reader container, not only the first match.

isReader() decides between the reader and the browsing branch of the shell, and
navWanted(), candidates(), focusSweep() and the key handler all call it. It used
to test only the first element matching the reader selectors for visibility, so a
hidden stale container rendered ahead of the live one made the shell treat a
visible reader as a browsing page.

The only differences from the old first-match check are exactly the cases where
a hidden container precedes a visible one, on non-reader routes. This runs in
real Chromium because it depends on document order and computed style.
"""
import pathlib
import re
import unittest

from playwright.sync_api import sync_playwright


ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "extension/content.js").read_text(encoding="utf-8")
BODY = re.search(r"function isReader\(\) \{(.*?)\n  \}", SOURCE, re.S).group(1)

HELPERS = """
window.__shown = function (e) {
  if (!e || !e.isConnected) return false;
  const r = e.getBoundingClientRect();
  if (r.width < 18 || r.height < 14) return false;
  const cs = getComputedStyle(e);
  if (cs.display === 'none' || cs.visibility === 'hidden') return false;
  return parseFloat(cs.opacity || '1') >= 0.04;
};
"""

OLD = """(path) => {
  const shown = window.__shown;
  const reader = document.querySelector('.wr_horizontalReader,.readerChapterContent_container');
  return /^\\/web\\/reader\\//.test(path) || !!(reader && shown(reader));
}"""

NEW = """([path, body]) => {
  const $$ = (s) => Array.prototype.slice.call(document.querySelectorAll(s));
  const shown = window.__shown;
  const location = { pathname: path };
  return eval('(function() {' + body + '\\n})')();
}"""

CASES = [
    # (name, html, differs_from_old)
    ("no containers", "", False),
    ("single visible", "<div class='wr_horizontalReader'>x</div>", False),
    ("single hidden", "<div class='wr_horizontalReader' style='display:none'>x</div>", False),
    ("hidden stale first, visible second",
     "<div class='readerChapterContent_container' style='display:none'>old</div>"
     "<div class='wr_horizontalReader'>new</div>", True),
    ("visible first, hidden second",
     "<div class='wr_horizontalReader'>new</div>"
     "<div class='readerChapterContent_container' style='display:none'>old</div>", False),
    ("all hidden",
     "<div class='wr_horizontalReader' style='display:none'>a</div>"
     "<div class='readerChapterContent_container' style='display:none'>b</div>", False),
    ("zero size container", "<div class='wr_horizontalReader'></div>", False),
    ("transparent container", "<div class='wr_horizontalReader' style='opacity:0'>x</div>", False),
    ("middle of three visible",
     "<div class='wr_horizontalReader' style='display:none'>a</div>"
     "<div class='readerChapterContent_container'>b</div>"
     "<div class='wr_horizontalReader' style='display:none'>c</div>", True),
]

PATHS = ("/web/shelf", "/web/reader/abc123", "/", "/web/category/100000")

SCAFFOLD = ("<style>.wr_horizontalReader,.readerChapterContent_container"
            "{display:block;min-width:100px;min-height:60px}</style>"
            "<body style='margin:0'>%s</body>")


class IsReaderBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.pw = sync_playwright().start()
            cls.browser = cls.pw.chromium.launch()
        except Exception as error:  # pragma: no cover - environment dependent
            raise unittest.SkipTest("chromium is not available: %s" % error)
        cls.page = cls.browser.new_page()
        cls.page.set_viewport_size({"width": 640, "height": 480})

    @classmethod
    def tearDownClass(cls):
        try:
            cls.browser.close()
            cls.pw.stop()
        except Exception:
            pass

    def run_case(self, html, path):
        self.page.set_content(SCAFFOLD % html)
        self.page.add_script_tag(content=HELPERS)
        old = self.page.evaluate(OLD, path)
        new = self.page.evaluate(NEW, [path, BODY])
        return bool(old), bool(new)

    def test_visible_reader_is_found_behind_a_hidden_stale_container(self):
        for path in PATHS:
            for name, html, differs in CASES:
                old, new = self.run_case(html, path)
                on_reader_route = path.startswith("/web/reader/")
                # On the reader route the old check already returned true, so
                # there is nothing to differ. Elsewhere only the two
                # hidden-before-visible cases may change.
                if on_reader_route or not differs:
                    self.assertEqual(old, new, "%s at %s" % (name, path))
                else:
                    self.assertFalse(old, name)
                    self.assertTrue(new, name)

    def test_reader_route_always_wins(self):
        for name, html, _ in CASES:
            old, new = self.run_case(html, "/web/reader/abc")
            self.assertTrue(new, name)
            self.assertEqual(old, new, name)


class IsReaderSourceTests(unittest.TestCase):
    def test_reader_check_scans_every_container(self):
        self.assertIn("$$('.wr_horizontalReader,.readerChapterContent_container')", BODY)
        self.assertIn("for (var i = 0; i < found.length; i++) if (shown(found[i])) return true;", BODY)
        self.assertNotIn("var reader = $('.wr_horizontalReader", BODY)

    def test_reader_route_still_wins_without_any_container(self):
        self.assertIn("if (/\\/web\\/reader\\//.test(location.pathname)) return true;", BODY)


if __name__ == "__main__":
    unittest.main()