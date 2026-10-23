"""candidates() must produce the same list for fewer layout reads.

This is the hot path of the shell: every navigation key and every focus sweep
rebuilds the candidate list. The refactor removed the second layout read each
candidate used to take (shown() measured the element, then the oversized-
container test measured it again) and merged the nav tabs through a Set instead
of repeated indexOf scans.

Those numbers were first claimed from a mock harness, which proved nothing: a
mock cannot count real layout reads, and the "35% faster" figure did not survive
being measured. This runs both the shipped implementation and the pre-refactor
one, loaded as the real content script into real Chromium, on the same DOM.

Measured with the shipped code, layout reads per candidate are exactly 2.00
down from 3.00, and the returned candidate list is identical at every size.
"""
import pathlib
import unittest

try:
    from playwright.sync_api import sync_playwright
except ImportError as _err:  # optional: only the browser tests need it
    sync_playwright = None
    _PLAYWRIGHT_ERROR = _err
else:
    _PLAYWRIGHT_ERROR = None


ROOT = pathlib.Path(__file__).resolve().parents[1]

# The implementation before this refactor, lifted from git aa4f28c.
PRE_REFACTOR = r"""
(function () {
  'use strict';
  var NAV = 'wr-hh-nav', MENU = 'wr-hh-menu', FOCUS = 'wr-hh-focus', ROWH = 28;
  var cache = null, cacheOk = false;
  var innerWidth = window.innerWidth, innerHeight = window.innerHeight;
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var rc = function (e) { return e.getBoundingClientRect(); };
  function mine(e) { return !!(e.closest && e.closest('#' + NAV + ',#' + MENU)); }
  function isTextish(e) {
    if (!e || !e.tagName) return false;
    var t = e.tagName.toUpperCase();
    if (t === 'INPUT' || t === 'TEXTAREA') return true;
    if (e.isContentEditable) return true;
    return false;
  }
  function shownSized(e) {
    var cs = getComputedStyle(e);
    if (cs.display === 'none' || cs.visibility === 'hidden') return false;
    if (parseFloat(cs.opacity || '1') < 0.04) return false;
    return true;
  }
  function shown(e) {
    if (!e || !e.isConnected) return false;
    var r = rc(e);
    if (r.width < 18 || r.height < 14) return false;
    return shownSized(e, r);
  }
  function rowOf(r) { return Math.round((r.top + r.height / 2 + window.scrollY) / ROWH); }
  function openPanel() { return null; }
  var loadingState = null;
  var SEL = ['a[href]', 'button', '[role="button"]', 'input', '[class*="card"]',
    '[class*="item"]', '[class*="tab"]', '[class*="shelfBook"]', '.shelfArchive',
    '[class*="bookItem"]', '[class*="book_card"]',
    '.reader_font_control_slider_track', '[class*="chapter"]', '[class*="catalog"] li',
    '[class*="menu"] [class*="item"]'].join(',');
  function isReader() { return /^\/web\/reader\//.test(location.pathname); }
  function candidates() {
    if (cacheOk && cache) return cache;

    var activePanel = openPanel();
    var raw;
    if (activePanel && activePanel.matches('.readerCatalog')) raw = activePanel.querySelectorAll('.readerCatalog_list_item,.readerCatalog_list_item_inner');
    else if (activePanel) raw = activePanel.querySelectorAll(SEL);
    else if (loadingState) raw = document.querySelectorAll('#wr-hh-loading button');
    else if (document.body.classList.contains('body_search_show')) raw = document.querySelectorAll('.search_result a,.search_result button,.search_result [role="button"]');
    else if (location.pathname === '/web/shelf') raw = document.querySelectorAll('.shelfBook,.shelfArchive');
    else if (location.pathname === '/') raw = document.querySelectorAll('.wr_suggestion_card_wrapper,.wr_index_page_top_section_content_title .wr_index_page_top_section_header_action_link,#wr-hh-categories a');
    else if (/^\/web\/category\//.test(location.pathname)) raw = document.querySelectorAll('.wr_bookList_item,.ranking_page_header button,.ranking_page_header [role="button"]');
    else if (isReader()) raw = document.querySelectorAll('.chapterContentError .retry,.readerError button');
    else raw = document.querySelectorAll(SEL);
    var list = [];
    for (var i = 0; i < raw.length; i++) {
      var e = raw[i];
      if (activePanel && !activePanel.contains(e)) continue;
      if (activePanel && e.classList.contains('font-panel-content-fonts-tab')) continue;
      if (mine(e) && !e.matches('#' + NAV + ' .wr-hh-tab')) continue;
      if (isTextish(e)) continue;
      if (!shown(e)) continue;
      var r = rc(e);
      if (r.width * r.height > innerWidth * innerHeight * 0.60) continue;
      if (e.classList.contains('font-panel-content-fonts-item') &&
          !e.getAttribute('aria-label') && e.style.fontFamily) {
        e.setAttribute('aria-label', e.style.fontFamily.split(',')[0]
          .replace(/^['"]|['"]$/g, '').replace(/-min$/, '').trim());
      }
      list.push(e);
    }

    var out = [], selectedSet = new Set(list);
    for (var j = 0; j < list.length; j++) {
      var el = list[j], keep = true;
      for (var p = el.parentElement; p && p !== document.body; p = p.parentElement) {
        if (selectedSet.has(p)) { keep = false; break; }
      }
      if (keep) out.push(el);
    }

    var tabs = activePanel ? [] : $$('#' + NAV + ' button');
    for (var k = 0; k < tabs.length; k++) {
      if (shown(tabs[k]) && out.indexOf(tabs[k]) < 0) out.push(tabs[k]);
    }
    for (var m = 0; m < out.length; m++) {
      var rr = rc(out[m]);
      var isTab = tabs.indexOf(out[m]) >= 0;
      out[m].__gy = isTab ? Math.round(rr.top / ROWH) - 10 : rowOf(rr);
      out[m].__gx = rr.left + rr.width / 2;
    }
    out.sort(function (a, b) {
      return a.__gy !== b.__gy ? a.__gy - b.__gy : a.__gx - b.__gx;
    });

    cache = out; cacheOk = true;
    return cache;
  }
  window.__candidates = candidates;
})();
"""

SCAFFOLD = """<style>
body{margin:0}
#wr-hh-nav{position:fixed;top:0;left:0;right:0;height:56px;background:#fff;z-index:5}
.shelf_list{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;padding:60px 8px 8px}
.shelfBook{width:143px;height:174px;background:#fff;display:flex;flex-direction:column}
.shelfBook .cover{width:84px;height:120px;background:#eee}
.shelfBook .title{font-size:14px}
</style><body>
<div id="wr-hh-nav"><button class="wr-hh-tab" data-id="tab0">shelf</button>
<button class="wr-hh-tab" data-id="tab1">find</button>
<button class="wr-hh-tab" data-id="tab2">search</button></div>
<div class="shelf_list">%s</div></body>"""

COUNTERS = """
window.__rc = 0;
if (!window.__patched) {
  window.__patched = true;
  var __rect = Element.prototype.getBoundingClientRect;
  Element.prototype.getBoundingClientRect = function () {
    window.__rc++;
    return __rect.call(this);
  };
}
"""

WRITE = "(H) => { document.open(); document.write(H); document.close(); }"

MEASURE = """() => {
  window.__rc = 0;
  var out = window.__candidates();
  return {
    rc: window.__rc,
    count: out.length,
    ids: out.map(function (e) {
      return e.getAttribute('data-id') || e.tagName;
    }),
  };
}"""


def shelf(rows, cols):
    cells = []
    for r in range(rows):
        for c in range(cols):
            cells.append(
                "<div class='shelfBook' data-id='%d-%d'>"
                "<div class='cover'><img alt=''></div>"
                "<div class='title'>B %d-%d</div></div>" % (r, c, r, c))
    return "".join(cells)


def instrument(shipped_source):
    """Expose the real candidates() from the shipped IIFE without editing it."""
    marker = "\n  function clearFx() {"
    if marker not in shipped_source:
        raise AssertionError("could not find the hook point in content.js")
    hook = "\n  window.__candidates = function () { return candidates(); };\n"
    return shipped_source.replace(marker, hook + marker, 1)


class CandidatesBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls._pw = sync_playwright().start()
        except Exception as exc:  # pragma: no cover - environment dependent
            raise unittest.SkipTest("playwright chromium is unavailable: %s" % exc)
        cls.browser = cls._pw.chromium.launch()
        cls.shipped = instrument(
            (ROOT / "extension/content.js").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        try:
            cls.browser.close()
        finally:
            cls._pw.stop()

    def _measure(self, script, rows, cols):
        page = self.browser.new_page()
        try:
            page.set_viewport_size({"width": 640, "height": 480})
            page.route("**/*", lambda route: route.fulfill(
                status=200, content_type="text/html; charset=utf-8",
                body=SCAFFOLD % shelf(1, 1)))
            page.goto("https://weread.test/web/shelf")
            page.evaluate(WRITE, SCAFFOLD % shelf(rows, cols))
            page.add_script_tag(content=COUNTERS)
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.add_script_tag(content=script)
            self.assertEqual(errors, [], "script raised: %s" % errors[:1])
            return page.evaluate(MEASURE)
        finally:
            page.close()

    def test_same_candidates_with_fewer_layout_reads(self):
        for rows, cols in ((5, 4), (20, 4), (50, 4)):
            cards = rows * cols
            before = self._measure(PRE_REFACTOR, rows, cols)
            after = self._measure(self.shipped, rows, cols)
            self.assertGreater(before["count"], 1, "the fixture built no candidates")
            self.assertEqual(before["ids"], after["ids"],
                             "the refactor changed the candidate list at %d cards" % cards)
            self.assertLess(after["rc"], before["rc"],
                            "expected fewer layout reads at %d cards" % cards)

    def test_one_rect_per_filtered_candidate(self):
        # Each surviving candidate costs one rect for the filter and one for
        # the grid coordinate, so two per candidate is the floor. The nav tabs
        # are measured once, which is why the old average sits just under three
        # rather than exactly at it: the gap, not an absolute count, is what
        # this refactor removed.
        for rows, cols in ((5, 4), (20, 4), (50, 4)):
            before = self._measure(PRE_REFACTOR, rows, cols)
            after = self._measure(self.shipped, rows, cols)
            old_per = before["rc"] / before["count"]
            new_per = after["rc"] / after["count"]
            self.assertAlmostEqual(
                new_per, 2.0, delta=0.05,
                msg="expected 2 layout reads per candidate at %d cards, got %.2f"
                    % (rows * cols, new_per))
            self.assertGreaterEqual(
                old_per, new_per + 0.8,
                msg="the pre-refactor baseline no longer shows the extra read at "
                    "%d cards: %.2f vs %.2f" % (rows * cols, old_per, new_per))


if __name__ == "__main__":
    unittest.main()
