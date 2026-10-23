"""The bridge's native-input mark must survive overlapping actions.

input_bridge.py is a ThreadingHTTPServer on purpose, so several gamepad
actions can be in flight at once. The catalog and settings actions all set the
same attribute on .readerControls, which is the only thing making the site's
invisible toolbar clickable, and all clear it when they finish.

A bare boolean is safe only by luck of timing. Clear it while another action
sits between mousePressed and mouseReleased and that click is dispatched
against a toolbar with pointer-events disabled, which is the "X does nothing"
symptom the attribute exists to prevent. So the mark counts holders and is only
removed by the last one.

The attribute name is load-bearing in both directions: the bridge sets it with
setAttribute and the stylesheet matches it as [data-...]. Writing the name
without the data- prefix sets a different attribute, and the toolbar stays
invisible to synthetic clicks with no error anywhere to show for it.
"""
import importlib.util
import pathlib
import re
import shutil
import tempfile
import unittest

try:
    from playwright.sync_api import sync_playwright
except ImportError as _err:  # optional: only the browser tests need it
    sync_playwright = None
    _PLAYWRIGHT_ERROR = _err
else:
    _PLAYWRIGHT_ERROR = None


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_bridge():
    """Import input_bridge.py the way the device does, with its own cdp stub.

    input_bridge.py inserts its own directory at the front of sys.path and then
    does `import cdp`, so the first bridge loaded in a process owns the global
    "cdp" module name for every bridge loaded after it. Loading this one in
    isolation keeps the tests independent of execution order.
    """
    stub = "def pick_page_target():\n    return None\n\n\nclass WS:\n    pass\n"
    directory = tempfile.mkdtemp()
    (pathlib.Path(directory) / "cdp.py").write_text(stub, encoding="utf-8")
    local = pathlib.Path(directory) / "input_bridge.py"
    shutil.copy(ROOT / "launcher" / "input_bridge.py", local)
    spec = importlib.util.spec_from_file_location(
        "input_bridge_native_input_under_test", local)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bridge = load_bridge()

CSS = (ROOT / "extension" / "shell.css").read_text(encoding="utf-8")
MARK = bridge.NATIVE_INPUT_MARK

# The site toolbar markup, plus the shipped stylesheet verbatim so the cascade
# under test is the real one.
PAGE = ("<html><head><style>" + CSS + "</style></head><body>"
        "<div class=\"readerControls readerControls\" id=\"rc\">"
        "<button class=\"readerControls_item catalog\" id=\"btn\">x</button>"
        "</div></body></html>")

STATE = """(mark) => {
  const rc = document.querySelector('.readerControls');
  return {
    mark: rc.getAttribute(mark),
    pointerEvents: getComputedStyle(rc).pointerEvents,
    clickable: getComputedStyle(rc).pointerEvents !== 'none',
  };
}"""


class NativeInputMarkTests(unittest.TestCase):
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

    def setUp(self):
        self.page = self.browser.new_page()
        self.page.route("**/*", lambda route: route.fulfill(
            status=200, content_type="text/html; charset=utf-8", body=PAGE))
        self.page.goto("https://weread.qq.com/web/reader/x")

    def tearDown(self):
        self.page.close()

    def state(self):
        return self.page.evaluate(STATE, MARK)

    def test_the_mark_is_a_holder_count_not_a_flag(self):
        counts = []
        for _ in range(3):
            counts.append(self.page.evaluate(bridge._hold_native_input_source()))
        self.assertEqual(counts, [1, 2, 3])
        for value in (2, 1):
            self.page.evaluate(bridge._release_native_input_source())
            self.assertEqual(self.state()["mark"], str(value))
        self.page.evaluate(bridge._release_native_input_source())
        self.assertIsNone(self.state()["mark"])

    def test_toolbar_stays_clickable_until_the_last_holder_releases(self):
        self.assertFalse(self.state()["clickable"])
        for _ in range(3):
            self.page.evaluate(bridge._hold_native_input_source())
        self.page.evaluate(bridge._release_native_input_source())
        self.page.evaluate(bridge._release_native_input_source())
        self.assertTrue(self.state()["clickable"],
                        "the toolbar went unclickable while a holder remained")
        self.page.evaluate(bridge._release_native_input_source())
        self.assertFalse(self.state()["clickable"])

    def test_release_without_a_holder_is_harmless(self):
        self.page.evaluate(bridge._hold_native_input_source())
        self.page.evaluate(bridge._release_native_input_source())
        self.assertIsNone(self.state()["mark"])
        for _ in range(3):
            self.assertEqual(self.page.evaluate(
                bridge._release_native_input_source()), 0)
        self.assertIsNone(self.state()["mark"])
        self.assertFalse(self.state()["clickable"])


class NativeInputContractTests(unittest.TestCase):
    def setUp(self):
        self.bridge = (ROOT / "launcher" / "input_bridge.py").read_text(encoding="utf-8")

    def test_the_bridge_and_the_stylesheet_agree_on_the_attribute_name(self):
        self.assertIn("data-wr-hh-native-input-holders", self.bridge)
        self.assertIn("[data-wr-hh-native-input-holders]", CSS)

    def test_the_mark_carries_the_data_prefix(self):
        # The stylesheet matches [data-...]; setting the bare name silently
        # creates a different attribute and the toolbar never becomes clickable.
        self.assertTrue(bridge.NATIVE_INPUT_MARK.startswith("data-"))

    def test_cleanup_still_never_raises(self):
        block = re.search(r"finally:\n(.*?)\n        ws\.close\(\)", self.bridge, re.S)
        self.assertIsNotNone(block, "could not find the cleanup block")
        cleanup = block.group(1)
        self.assertIn("_release_native_input(ws, 5)", cleanup)
        self.assertIn("except (OSError, ValueError, KeyError, RuntimeError):", cleanup)

    def test_the_legacy_attribute_is_still_supported(self):
        # A device that has the new stylesheet but an old bridge on disk must
        # keep working, so the old selector stays.
        self.assertIn("[data-wr-hh-native-input]", CSS)


if __name__ == "__main__":
    unittest.main()
