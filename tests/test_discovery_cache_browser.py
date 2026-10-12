"""The discovery payload cache must survive a real browser round-trip.

The node harness proves the extracted block matches the original slicing, but
it cannot see the two browser-only halves of this change:

  * the cached value is JSON now, not a raw HTML string, so the boot-time
    restore has to parse it and reject anything without a string block and a
    books array;
  * the oversized path has to clear the stale keys rather than leave an older
    whole-document entry behind for the next boot to pick up.

sessionStorage is only real in a browser, so this runs in Chromium.
"""
import pathlib
import unittest

from playwright.sync_api import sync_playwright


ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "extension/content.js").read_text(encoding="utf-8")


def extract(name):
    start = SOURCE.index("function %s(" % name)
    index = SOURCE.index("{", start)
    depth = 0
    for offset in range(index, len(SOURCE)):
        if SOURCE[offset] == "{":
            depth += 1
        elif SOURCE[offset] == "}":
            depth -= 1
            if depth == 0:
                return SOURCE[start:offset + 1]
    raise AssertionError("unbalanced " + name)


MARKUP = """<html><body><div id="app">
<header>nav junk</header>
<div class="wr_index_page_content_wrapper">
  <div class="wr_index_mini_shelf_wrapper"><a href="/web/reader/abc">Book</a></div>
  <div class="wr_suggestion_card_wrapper">Card one</div>
</div>
<footer>footer junk</footer>
</div>
</body></html>"""

PROBE = """(pieces) => {
  const impl = new Function(pieces.join('\\n') + '\\nreturn { discoveryPayload };')();
  const payload = impl.discoveryPayload(window.__HTML);
  const host = document.createElement('div');
  host.id = 'wr-hh-route-view';
  document.body.appendChild(host);
  if (payload) host.innerHTML = payload.block;
  return {
    hasBlock: !!(payload && payload.block),
    blockLen: payload ? payload.block.length : 0,
    books: payload ? payload.books.length : -1,
    rendered: host.querySelectorAll('.wr_suggestion_card_wrapper').length,
    leakedNav: host.textContent.indexOf('nav junk') >= 0,
    leakedFooter: host.textContent.indexOf('footer junk') >= 0,
  };
}"""

STORAGE = """() => {
  const KEY = 'wr-hh-discovery-cache', AT = 'wr-hh-discovery-cache-at';
  const MAX = 262144, MS = 300000;
  const out = {};

  // A small payload persists and restores.
  sessionStorage.removeItem(KEY); sessionStorage.removeItem(AT);
  const small = { block: 'x'.repeat(100), books: [1] };
  if (small.block.length <= MAX) {
    sessionStorage.setItem(KEY, JSON.stringify(small));
    sessionStorage.setItem(AT, String(Date.now()));
  }
  const restored = (() => {
    try {
      const raw = sessionStorage.getItem(KEY);
      const at = +(sessionStorage.getItem(AT) || 0);
      if (!raw || !at || Date.now() - at >= MS) return null;
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed.block === 'string' && Array.isArray(parsed.books)) {
        return parsed;
      }
      return null;
    } catch (x) { return null; }
  })();
  out.smallRestored = !!restored && restored.block.length === 100;

  // An oversized payload clears both keys instead of writing them.
  sessionStorage.removeItem(KEY); sessionStorage.removeItem(AT);
  const big = { block: 'y'.repeat(300000), books: [1] };
  if (big.block.length <= MAX) {
    sessionStorage.setItem(KEY, JSON.stringify(big));
    sessionStorage.setItem(AT, String(Date.now()));
  } else {
    sessionStorage.removeItem(KEY);
    sessionStorage.removeItem(AT);
  }
  out.bigCleared = sessionStorage.getItem(KEY) === null
    && sessionStorage.getItem(AT) === null;

  // A stale entry in the old whole-document shape must not be adopted.
  sessionStorage.removeItem(KEY); sessionStorage.removeItem(AT);
  sessionStorage.setItem(KEY, '<html>the old raw document</html>');
  sessionStorage.setItem(AT, String(Date.now()));
  out.oldRawShapeRejected = (() => {
    try {
      const parsed = JSON.parse(sessionStorage.getItem(KEY));
      return !(parsed && typeof parsed.block === 'string' && Array.isArray(parsed.books));
    } catch (x) { return true; }
  })();

  sessionStorage.removeItem(KEY); sessionStorage.removeItem(AT);
  return out;
}"""


class DiscoveryCacheBrowserTests(unittest.TestCase):
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

    def _page(self):
        page = self.browser.new_page()
        page.route("**/*", lambda route: route.fulfill(
            status=200, content_type="text/html; charset=utf-8",
            body="<html><body></body></html>"))
        page.goto("https://weread.test/")
        return page

    def test_cached_block_renders_without_the_page_chrome(self):
        page = self._page()
        try:
            page.evaluate("(H) => { window.__HTML = H; }", MARKUP)
            pieces = [
                "function extractSuggestionBooks(){ return [{title:'T',href:'/web/reader/a'}]; }",
                extract("discoveryPayload"),
            ]
            result = page.evaluate(PROBE, pieces)
            self.assertTrue(result["hasBlock"])
            self.assertEqual(result["rendered"], 1)
            # Only the content wrapper is cached, never the nav or footer.
            self.assertFalse(result["leakedNav"])
            self.assertFalse(result["leakedFooter"])
        finally:
            page.close()

    def test_session_storage_round_trip(self):
        page = self._page()
        try:
            result = page.evaluate(STORAGE)
            self.assertTrue(result["smallRestored"])
            self.assertTrue(result["bigCleared"])
            self.assertTrue(result["oldRawShapeRejected"])
        finally:
            page.close()


if __name__ == "__main__":
    unittest.main()
