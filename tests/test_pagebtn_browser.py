"""pageBtn() must return exactly the element the original lookup returned.

The returned element is what gets clicked to turn the page, so a difference is a
behaviour change, not a detail. This runs the shipped implementation and the
pre-refactor implementation side by side in real Chromium.

A mock harness was tried first and was not sufficient: it could not model two
things that actually matter here.

  * textContent on an element with children returns the concatenated text of
    every descendant, so a wrapper matches the label before the label does.
  * ":empty" only matches elements with no child nodes at all. A label is a
    text node, so :empty never matches it, and appending :empty to a
    comma-separated selector list silently applies it to the last branch only,
    which left every earlier tag unfiltered.

Between them those turned an optimisation into a lookup that clicked the
enclosing wrapper instead of the page turner. The children check has to come
before the text comparison, and this test is what proves it.

The tag list is deliberately unchanged from the original span,div,a,button.
Widening it was tried and reverted: it is not a superset, it also matches
elements the original could never find, which changes what gets clicked.
"""
import json
import pathlib
import re
import unittest

from playwright.sync_api import sync_playwright


ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "extension/content.js").read_text(encoding="utf-8")
SELECTOR = re.search(r"var PAGE_LABEL_SEL =\s*'([^']+)'", SOURCE).group(1)
BODY = re.search(r"function pageBtn\(dir\) \{(.*?)\n  \}\n", SOURCE, re.S).group(1)

# The implementation before this refactor, verbatim.
OLD = """(want) => {
  var NAV = 'wr-hh-nav', MENU = 'wr-hh-menu';
  function shown(e) {
    if (!e || !e.isConnected) return false;
    var r = e.getBoundingClientRect();
    if (r.width < 18 || r.height < 14) return false;
    var cs = getComputedStyle(e);
    if (cs.display === 'none' || cs.visibility === 'hidden') return false;
    return parseFloat(cs.opacity || '1') >= 0.04;
  }
  function mine(e) { return !!(e.closest && e.closest('#' + NAV + ',#' + MENU + ',#wr-hh-kbd')); }
  var pCache = {};
  var els = document.querySelectorAll('span,div,a,button');
  for (var j = 0; j < els.length; j++) {
    var e = els[j];
    if (e.children.length) continue;
    if ((e.innerText || '').trim() !== want) continue;
    if (!shown(e) || mine(e)) continue;
    pCache[want] = e;
    return { found: true, tag: e.tagName, text: e.innerText.trim() };
  }
  return { found: false };
}"""

NEW = """([want, sel, body]) => {
  var PAGE_LABEL_SEL = sel;
  var pCache = {};
  var NAV = 'wr-hh-nav', MENU = 'wr-hh-menu';
  function shown(e) {
    if (!e || !e.isConnected) return false;
    var r = e.getBoundingClientRect();
    if (r.width < 18 || r.height < 14) return false;
    var cs = getComputedStyle(e);
    if (cs.display === 'none' || cs.visibility === 'hidden') return false;
    return parseFloat(cs.opacity || '1') >= 0.04;
  }
  function mine(e) { return !!(e.closest && e.closest('#' + NAV + ',#' + MENU + ',#wr-hh-kbd')); }
  var pageBtn = eval('(function(dir){' + body + '\\n})');
  var e = pageBtn(want === '\\u4e0b\\u4e00\\u9875' ? 'next' : 'prev');
  if (!e) return { found: false };
  return { found: true, tag: e.tagName, text: e.textContent.trim() };
}"""

NEXT = "\u4e0b\u4e00\u9875"
PREV = "\u4e0a\u4e00\u9875"

CASES = [
    ("plain text node", "<span>%s</span>" % NEXT),
    ("whitespace around", "<span>  %s  </span>" % NEXT),
    ("text split by comment", "<span>\u4e0b<!--c-->\u4e00\u9875</span>"),
    ("leading newline indent", "\n  <span>%s</span>\n" % NEXT),
    ("nested span inside span", "<span><span>%s</span></span>" % NEXT),
    ("nbsp padding", "<span>&nbsp;%s&nbsp;</span>" % NEXT),
    ("button label", "<button>%s</button>" % NEXT),
    ("anchor label", "<a href='#'>%s</a>" % NEXT),
    ("div label leaf", "<div>%s</div>" % NEXT),
    ("two labels", "<span>%s</span><span>%s</span>" % (PREV, NEXT)),
    ("hidden first visible second",
     "<span style='display:none'>%s</span><span>%s</span>" % (NEXT, NEXT)),
    ("page furniture", "<span>\u7b2c\u4e00\u9875</span><span>\u5171 3 \u9875</span>"),
    ("no label", "<span>\u6ca1\u6709</span>"),
    ("label deep in tree", "<div><section><p><em>%s</em></p></section></div>" % NEXT),
    ("wrapper with icon then text", "<span><i class='ic'></i>%s</span>" % NEXT),
    ("aria-label only", "<span aria-label='%s'></span>" % NEXT),
    ("shell-owned node", "<div id='wr-hh-nav'><span>%s</span></div>" % NEXT),
    ("reader footer around label",
     "<div class='readerControls'><span>\u76ee\u5f55</span></div>"
     "<div class='reader_footer'><span>%s</span><span>%s</span></div>" % (PREV, NEXT)),
    ("label after other text", "<span>\u4e66\u540d</span><span>%s</span>" % NEXT),
    ("prev only", "<span>%s</span>" % PREV),
    ("em label", "<em>%s</em>" % NEXT),
    ("label inside nav-adjacent wrapper",
     "<div class='reader_footer'><div class='inner'><span>%s</span></div></div>" % NEXT),
]

SCAFFOLD = (
    "<style>span,div,a,button,em,strong,i,label,p,li,cite,figcaption,section,"
    "img,hr,h1,h2,h3,h4,h5,h6,u,s,small,center,output,summary,legend,caption,dt,"
    "dd,th,td,code,kbd,samp,var,q,abbr,sub,sup,mark,time,data,bdi,bdo,ruby,rt,rp"
    "{display:inline-block;min-width:24px;min-height:18px;padding:2px}"
    ".inner{display:inline-block}</style>"
    "<body style='margin:0'><div class=host>%s</div></body>"
)


class PageButtonBrowserTests(unittest.TestCase):
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

    def test_lookup_matches_the_original_for_every_case(self):
        for name, html in CASES:
            self.page.set_content(SCAFFOLD % html)
            for want in (NEXT, PREV):
                old = self.page.evaluate(OLD, want)
                new = self.page.evaluate(NEW, [want, SELECTOR, BODY])
                self.assertEqual(old["found"], new["found"],
                                 "%s / %s" % (name, json.dumps(want, ensure_ascii=False)))
                self.assertEqual(old.get("tag"), new.get("tag"),
                                 "%s / %s" % (name, json.dumps(want, ensure_ascii=False)))

    def test_leaf_text_content_equals_inner_text(self):
        # The reason textContent may replace innerText at all: on an element
        # with no element children the two agree.
        self.page.set_content("<body><span id=s>  %s  </span></body>" % NEXT)
        result = self.page.evaluate(
            "() => { const s = document.getElementById('s');"
            " return s.children.length === 0"
            "   && s.textContent.trim() === s.innerText.trim(); }")
        self.assertTrue(result)

    def test_a_wrapper_never_wins_over_the_label(self):
        # textContent on a container is the text of all its descendants, so
        # without the children check the enclosing div would be returned and
        # the click would land on the wrapper.
        self.page.set_content(SCAFFOLD % ("<div class=wrap><span>%s</span></div>" % NEXT))
        new = self.page.evaluate(NEW, [NEXT, SELECTOR, BODY])
        self.assertTrue(new["found"])
        self.assertEqual(new["tag"], "SPAN")


class PageButtonSourceTests(unittest.TestCase):
    def test_children_check_precedes_the_text_comparison(self):
        body = re.search(r"function pageBtn\(dir\) \{(.*?)\n  \}\n", SOURCE, re.S).group(1)
        self.assertLess(body.index("if (e.children.length) continue;"),
                        body.index("e.textContent"))

    def test_lookup_no_longer_reads_rendered_text(self):
        body = re.search(r"function pageBtn\(dir\) \{(.*?)\n  \}\n", SOURCE, re.S).group(1)
        self.assertNotIn("e.innerText", body)
        self.assertIn("(e.textContent || '').trim()", body)

    def test_empty_pseudo_class_is_not_used(self):
        # :empty never matches a text-only label and only filters the last
        # branch of a comma-separated list.
        self.assertNotIn(":empty", BODY)

    def test_tag_list_matches_the_original(self):
        self.assertEqual(SELECTOR, "span,div,a,button")


if __name__ == "__main__":
    unittest.main()
