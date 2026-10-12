"""The boot mask must never outlive a document that failed to finish loading.

The shell puts a full-viewport mask up at document_start and hides every page
element behind it until `wr-hh-boot-ready` lands (shell.css). The only release
used to be requestAnimationFrame(releaseBootMask) inside boot(), and boot() is
gated on DOMContentLoaded. The site loads a payment widget synchronously in
<head>, so a stalled host meant the mask went up, the release never ran, and the
handheld sat on a blank screen that no key could drive. guardHeadStall reloads
only once per session, so a second stall was terminal.

Chromium always synthesises a <body>, so the stalled state is produced the way a
crashed parser leaves it: a document whose body is gone. That is exactly the
shape guardBootMask() has to survive.
"""
import pathlib
import re
import unittest

from playwright.sync_api import sync_playwright


ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTENT = (ROOT / "extension/content.js").read_text(encoding="utf-8")
CSS = (ROOT / "extension/shell.css").read_text(encoding="utf-8")

PAGE = "<!doctype html><html><head></head><body><div id='site'>shelf</div></body></html>"

# Strip the body the way an aborted parse leaves the document. `script` keeps the
# content-script running, so the watchdog is live for the whole test.
STRIP_BODY = """
document.documentElement.innerHTML = '<head></head>';
if (document.body) document.body.remove();
"""


class BootMaskSourceTests(unittest.TestCase):
    """The watchdog must exist, and it must not live inside boot()."""

    def test_a_boot_mask_watchdog_exists(self):
        self.assertIn("function guardBootMask", CONTENT)

    def test_the_watchdog_runs_before_boot(self):
        # Inside boot() it would never run in the stalled case, because boot()
        # itself is what never runs.
        self.assertLess(CONTENT.index("function guardBootMask"),
                        CONTENT.index("  function boot() {"))

    def test_the_watchdog_notices_a_bodyless_document(self):
        self.assertIn("return !document.body;", CONTENT)

    def test_reload_budget_is_bounded(self):
        # An unbounded retry would reload forever against a permanently dead host.
        match = re.search(r"var MAX_RETRIES = (\d+)", CONTENT)
        self.assertIsNotNone(match)
        self.assertLessEqual(int(match.group(1)), 3)

    def test_a_manual_escape_hatch_is_wired(self):
        # After the budget is spent the user must keep a working way out.
        self.assertIn("\u52a0\u8f7d\u672a\u5b8c\u6210", CONTENT)
        self.assertIn("document.removeEventListener('keydown', onRetry, true)", CONTENT)

    def test_the_timer_cannot_hot_loop(self):
        # Every tick reschedules at most once, and only on the reload branch.
        self.assertEqual(CONTENT.count("setTimeout(tick, STALL_MS);"), 1)

    def test_a_successful_load_clears_the_budget(self):
        self.assertIn("function settle()", CONTENT)
        self.assertIn("clearRetries();", CONTENT)

    def test_release_still_happens_on_the_normal_path(self):
        # The watchdog supplements boot(); it must not replace it.
        self.assertIn("requestAnimationFrame(releaseBootMask);", CONTENT)


class BootMaskBrowserTests(unittest.TestCase):
    """Behavioural check in real Chromium, driven past the stall window."""

    @classmethod
    def setUpClass(cls):
        try:
            cls._pw = sync_playwright().start()
            cls.browser = cls._pw.chromium.launch()
        except Exception as exc:                       # pragma: no cover
            raise unittest.SkipTest("playwright chromium is unavailable: %s" % exc)

    @classmethod
    def tearDownClass(cls):
        browser = getattr(cls, "browser", None)
        if browser is not None:
            browser.close()
        pw = getattr(cls, "_pw", None)
        if pw is not None:
            pw.stop()

    def load_shell(self):
        """A healthy page running the real content.js."""
        page = self.browser.new_page()
        page.set_content(PAGE)
        page.add_script_tag(content=CONTENT)
        return page

    def state(self, page):
        return page.evaluate("""() => ({
          hasBody: !!document.body,
          mask: !!document.getElementById('wr-hh-boot-mask'),
          bootReady: document.documentElement.classList.contains('wr-hh-boot-ready')
        })""")

    def test_a_healthy_page_ends_ready_with_no_mask(self):
        page = self.load_shell()
        try:
            page.wait_for_function(
                "() => !document.getElementById('wr-hh-boot-mask')", timeout=5000)
            state = self.state(page)
            self.assertTrue(state["hasBody"])
            self.assertFalse(state["mask"])
            self.assertTrue(state["bootReady"])
        finally:
            page.close()

    def test_the_mask_is_up_before_the_page_is_ready(self):
        # Premise of the bug: the mask really does go up first. Observed
        # synchronously inside the same script, because the normal path releases
        # it within a frame and a polling wait would race that.
        page = self.browser.new_page()
        try:
            page.set_content(PAGE)
            seen = page.evaluate("""(content) => {
                var script = document.createElement('script');
                script.textContent = content +
                    ";window.__probe={mask: !!document.getElementById('wr-hh-boot-mask')," +
                    "ready: document.documentElement.classList.contains('wr-hh-boot-ready')};";
                document.body.appendChild(script);
                return window.__probe;
            }""", CONTENT)
            self.assertTrue(seen["mask"], "the boot mask should go up first")
            self.assertFalse(seen["ready"], "the page must not be ready yet")
        finally:
            page.close()

    def test_a_bodyless_document_does_not_end_in_a_blank_screen(self):
        """The regression: mask up, no body, and nothing ever releases it."""
        page = self.load_shell()
        try:
            page.wait_for_function(
                "() => !document.getElementById('wr-hh-boot-mask')", timeout=5000)
            # Now break the document the way an aborted parse would.
            page.evaluate(STRIP_BODY)
            page.evaluate("""() => {
                var mask = document.createElement('div');
                mask.id = 'wr-hh-boot-mask';
                document.documentElement.appendChild(mask);
            }""")
            self.assertFalse(self.state(page)["hasBody"], "setup: body must be gone")

            # Outlive the watchdog's first stall window plus a margin. Before the
            # fix the mask stayed on screen forever with no key able to help.
            page.wait_for_timeout(16000)
            after = self.state(page)
            self.assertTrue(
                after["mask"] is False or after["bootReady"],
                "the boot mask still covers a document that never loaded")
        finally:
            page.close()

    def test_the_escape_hatch_is_reachable_without_a_body(self):
        # The user has to be able to act while the document is broken, so confirm
        # document-level keydown still fires when there is no body.
        page = self.browser.new_page()
        try:
            page.set_content(PAGE)
            seen = page.evaluate("""() => {
                document.body.remove();
                var hit = null;
                document.addEventListener('keydown', e => { hit = e.key; }, true);
                document.dispatchEvent(new KeyboardEvent('keydown',
                                        {key: 'Enter', bubbles: true}));
                return { hit: hit, hasBody: !!document.body };
            }""")
            self.assertFalse(seen["hasBody"])
            self.assertEqual(seen["hit"], "Enter")
        finally:
            page.close()


class BootMaskPremiseTests(unittest.TestCase):
    def test_the_mask_is_an_opaque_full_viewport_cover(self):
        # Guards why an unreleased mask reads as a white screen: shell.css hides
        # every page element until boot-ready.
        self.assertIn(
            "html:not(.wr-hh-boot-ready) body > *:not(#wr-hh-boot-mask) "
            "{ visibility: hidden !important; }", CSS)
        self.assertIn("#wr-hh-boot-mask { position: fixed; inset: 0", CSS)


if __name__ == "__main__":
    unittest.main()
