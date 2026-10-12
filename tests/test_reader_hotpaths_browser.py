"""The annotation and panel-close paths must measure each element once.

Both of these run while the reader is on screen, on every comment step and on
every B press:

  * annotationItems() re-measured both elements on every sort comparison, which
    is O(n log n) layout reads on a heavily annotated chapter, and it measured
    and styled every wrapper including the ones it then discarded.
  * floatPanelCloseButton() called rc(e) and then shown(e), measuring the same
    element twice for every candidate.

Both now take one measurement and reuse it. Two things have to survive that:

  * the order annotationItems() returns, which decides which comment the shell
    focuses first;
  * shown()'s 18x14 minimum inside floatPanelCloseButton(), which the refactor
    dropped. Without it a tiny close button between 8px and 18px started being
    clicked, because the 8x8 test that remains is the looser of the two.

Measured in real Chromium: annotationItems() goes from ~8.5 layout reads per
wrapper to exactly 1 (332 -> 40 at 40 wrappers, 1018 -> 120 at 120), with an
identical returned order.
"""
import pathlib
import re
import unittest

from playwright.sync_api import sync_playwright


ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "extension/content.js").read_text(encoding="utf-8")

COUNTERS = """
window.__rc = 0;
window.__gcs = 0;
if (!window.__patched) {
  window.__patched = true;
  const __r = Element.prototype.getBoundingClientRect;
  Element.prototype.getBoundingClientRect = function () {
    window.__rc++; return __r.call(this);
  };
  const __g = window.getComputedStyle.bind(window);
  window.getComputedStyle = function () {
    window.__gcs++; return __g.apply(window, arguments);
  };
}
"""

ANNOTATION_PROBE = """(payload) => {
  const rc = (e) => e.getBoundingClientRect();
  const $$ = (s) => Array.prototype.slice.call(document.querySelectorAll(s));
  const hasNav = () => !!document.getElementById('wr-hh-nav');
  const impl = new Function('rc', '$$', 'innerWidth', 'innerHeight', 'hasNav', 'NAV',
                           payload.body + String.fromCharCode(10) + 'return annotationItems;')(
    rc, $$, window.innerWidth, window.innerHeight, hasNav, 'wr-hh-nav');
  window.__rc = 0; window.__gcs = 0;
  const out = impl();
  return {
    rc: window.__rc, gcs: window.__gcs, count: out.length,
    order: out.map((e) => e.getAttribute('data-id')),
  };
}"""

CLOSE_OLD = r"""() => {
  const rc = (e) => e.getBoundingClientRect();
  const $$ = (s) => Array.prototype.slice.call(document.querySelectorAll(s));
  const shownSized = (e, r) => {
    const cs = getComputedStyle(e);
    if (cs.display === 'none' || cs.visibility === 'hidden') return false;
    if (parseFloat(cs.opacity || '1') < 0.04) return false;
    return true;
  };
  const shown = (e) => {
    if (!e || !e.isConnected) return false;
    const r = rc(e);
    if (r.width < 18 || r.height < 14) return false;
    return shownSized(e, r);
  };
  const selectors = ['.reader_float_panel_header_closeBtn',
    '[class*="float_panel"] [class*="closeBtn"]',
    '[class*="float_panel"] [class*="close"]'];
  const panel = document.querySelector('.readerCatalog');
  if (!panel) return null;
  for (let i = 0; i < selectors.length; i++) {
    const list = $$(selectors[i]);
    for (let j = 0; j < list.length; j++) {
      const e = list[j], r = rc(e);
      if (!e.isConnected || !shown(e) || r.width < 8 || r.height < 8) continue;
      if (!panel.contains(e) && !e.closest('[class*="float_panel"]')) continue;
      return e;
    }
  }
  return null;
}"""

CLOSE_NEW = r"""() => {
  const rc = (e) => e.getBoundingClientRect();
  const $$ = (s) => Array.prototype.slice.call(document.querySelectorAll(s));
  const shownSized = (e, r) => {
    const cs = getComputedStyle(e);
    if (cs.display === 'none' || cs.visibility === 'hidden') return false;
    if (parseFloat(cs.opacity || '1') < 0.04) return false;
    return true;
  };
  const selectors = ['.reader_float_panel_header_closeBtn',
    '[class*="float_panel"] [class*="closeBtn"]',
    '[class*="float_panel"] [class*="close"]'];
  const panel = document.querySelector('.readerCatalog');
  if (!panel) return null;
  for (let i = 0; i < selectors.length; i++) {
    const list = $$(selectors[i]);
    for (let j = 0; j < list.length; j++) {
      const e = list[j];
      if (!e.isConnected) continue;
      const r = rc(e);
      if (r.width < 18 || r.height < 14) continue;
      if (r.width < 8 || r.height < 8) continue;
      if (!shownSized(e, r)) continue;
      if (!panel.contains(e) && !e.closest('[class*="float_panel"]')) continue;
      return e;
    }
  }
  return null;
}"""

CLOSE_SIZES = [(40, 40), (30, 20), (20, 15), (18, 14), (17, 13), (12, 14),
               (18, 8), (8, 8), (7, 7)]

CLOSE_HEAD = ("<style>body{margin:0}"
              ".readerCatalog{position:fixed;left:100px;top:100px;")
CLOSE_TAIL = "width:200px;height:300px}</style><body><div class=\"readerCatalog\">"
CLOSE_BUTTON = ("<button class=\"reader_float_panel_header_closeBtn\" "
                "style=\"width:Wpx;height:Hpx\"></button></div></body>")

HIDDEN_CASES = """<style>body{margin:0}
#wr-hh-nav{position:fixed;top:0;left:0;width:100%;height:56px;background:#eee}
</style><body>
<div id="wr-hh-nav"></div>
<div class="wr_underline_wrapper" data-id="a"
     style="position:absolute;top:80px;left:20px;width:80px;height:20px"></div>
<div class="wr_underline_wrapper" data-id="hidden-display" style="display:none"></div>
<div class="wr_underline_wrapper" data-id="hidden-visibility"
     style="visibility:hidden;position:absolute;top:100px;left:20px;width:80px;height:20px"></div>
<div class="wr_underline_wrapper" data-id="hidden-opacity"
     style="opacity:0;position:absolute;top:120px;left:20px;width:80px;height:20px"></div>
<div class="wr_underline_wrapper" data-id="behind-nav"
     style="position:absolute;top:10px;left:20px;width:80px;height:20px"></div>
<div class="wr_underline_wrapper" data-id="offscreen"
     style="position:absolute;top:200px;left:5000px;width:80px;height:20px"></div>
<div class="wr_underline_wrapper" data-id="b"
     style="position:absolute;top:80px;left:200px;width:80px;height:20px"></div>
</body>"""


def annotation_body(src):
    start = src.index("function annotationItems(")
    index = src.index("{", start)
    depth = 0
    for offset in range(index, len(src)):
        if src[offset] == "{":
            depth += 1
        elif src[offset] == "}":
            depth -= 1
            if depth == 0:
                return src[start:offset + 1]
    raise AssertionError("unbalanced annotationItems")


def wrappers(count, hidden):
    rows = []
    for i in range(count):
        if i < hidden:
            rows.append("<div class='wr_underline_wrapper' data-id='%d' "
                        "style='display:none;width:80px;height:20px'></div>" % i)
        else:
            rows.append(
                "<div class='wr_underline_wrapper' data-id='%d' "
                "style='position:absolute;top:%dpx;left:%dpx;width:80px;height:20px'></div>"
                % (i, 60 + (i % 12) * 24, 20 + (i % 5) * 100))
    return ("<style>body{margin:0}</style><body>"
            "<div id=\"wr-hh-nav\" style=\"position:fixed;top:0;left:0;width:100%;"
            "height:56px;background:#eee\"></div>" + "".join(rows) + "</body>")


class AnnotationBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls._pw = sync_playwright().start()
        except Exception as exc:  # pragma: no cover - environment dependent
            raise unittest.SkipTest("playwright chromium is unavailable: %s" % exc)
        cls.browser = cls._pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.browser.close()
        finally:
            cls._pw.stop()

    def _page(self, url="https://weread.test/web/reader/k"):
        page = self.browser.new_page()
        page.set_viewport_size({"width": 640, "height": 480})
        page.route("**/*", lambda route: route.fulfill(
            status=200, content_type="text/html; charset=utf-8",
            body="<html><body></body></html>"))
        page.goto(url)
        return page

    def _measure_annotations(self, page, count, hidden):
        page.evaluate("(H) => { document.open(); document.write(H); document.close(); }",
                      wrappers(count, hidden))
        page.add_script_tag(content=COUNTERS)
        return page.evaluate(ANNOTATION_PROBE, {"body": annotation_body(SOURCE)})

    def test_annotation_sort_reuses_the_measurement(self):
        block = re.search(r"function annotationItems\(\) \{(.*?)\n  \}",
                          SOURCE, re.S).group(1)
        # The comparator must not re-measure; it reads the cached rect.
        self.assertIn("var ar = a.__hhRect, br = b.__hhRect;", block)
        self.assertNotIn("rc(a), br = rc(b)", block)
        # The style read happens after the cheap rect tests.
        self.assertLess(block.index("var r = rc(e);"), block.index("var cs = getComputedStyle(e);"))

    def test_one_layout_read_per_wrapper(self):
        page = self._page()
        try:
            for count, hidden in ((40, 0), (120, 30)):
                result = self._measure_annotations(page, count, hidden)
                # One read per wrapper examined, plus one for the nav bar
                # whose bottom edge sets the annotation cutoff. A
                # display:none wrapper still costs its rect, because only
                # the style read was moved after the geometry tests.
                self.assertEqual(result["rc"], count + 1,
                                 "expected one layout read per wrapper at "
                                 "%d wrappers" % count)
        finally:
            page.close()

    def test_hidden_and_offscreen_wrappers_stay_excluded(self):
        page = self._page()
        try:
            page.evaluate("(H) => { document.open(); document.write(H); document.close(); }",
                          HIDDEN_CASES)
            page.add_script_tag(content=COUNTERS)
            result = page.evaluate(ANNOTATION_PROBE, {"body": annotation_body(SOURCE)})
            self.assertEqual(result["order"], ["a", "b"])
        finally:
            page.close()

    def test_tiny_close_button_is_still_rejected(self):
        """shown() enforced 18x14 on top of the 8x8 test. Dropping it let a
        button between the two thresholds through, and B would click it."""
        page = self._page()
        try:
            for w, h in CLOSE_SIZES:
                html = (CLOSE_HEAD + CLOSE_TAIL
                        + CLOSE_BUTTON.replace("W", str(w)).replace("H", str(h)))
                page.evaluate("(H) => { document.open(); document.write(H); document.close(); }",
                              html)
                old = page.evaluate(CLOSE_OLD) is not None
                new = page.evaluate(CLOSE_NEW) is not None
                self.assertEqual(old, new,
                                 "close-button choice changed at %dx%d" % (w, h))
        finally:
            page.close()

    def test_close_button_keeps_the_shown_size_floor(self):
        block = re.search(r"function floatPanelCloseButton\(\) \{(.*?)\n  \}",
                          SOURCE, re.S).group(1)
        # Both thresholds survive: the 18x14 floor from shown() and the 8x8
        # test the original loop also applied.
        self.assertIn("if (r.width < 18 || r.height < 14) continue;", block)
        self.assertIn("if (r.width < 8 || r.height < 8) continue;", block)
        self.assertNotIn("shown(e)", block)


if __name__ == "__main__":
    unittest.main()
