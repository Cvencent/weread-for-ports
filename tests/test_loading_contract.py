"""Contracts for one consistent loading experience when opening a book."""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class LoadingContractTests(unittest.TestCase):
    def setUp(self):
        self.js = (ROOT / "extension/content.js").read_text(encoding="utf-8")
        self.css = (ROOT / "extension/shell.css").read_text(encoding="utf-8")

    def test_boot_mask_reuses_the_shell_loading_visual(self):
        # The full-page boot mask must render the same spinner + text as #wr-hh-loading
        # so the user never sees two different loading designs in a row.
        self.assertIn('<span class="wr-hh-spinner" aria-hidden="true"></span>', self.js)
        self.assertNotIn("#wr-hh-boot-mask::before", self.css)
        self.assertIn("#wr-hh-boot-mask { position: fixed; inset: 0", self.css)

    def test_boot_mask_adopts_the_pending_navigation_text(self):
        # When a reader navigation is already in flight, the boot mask must say the
        # same thing as the shell overlay ("正在打开书籍"), not "正在加载微信读书".
        self.assertIn("function setBootMaskText", self.js)
        self.assertIn("setBootMaskText(pending.text)", self.js)

    def test_boot_mask_is_labelled_from_the_pending_state_at_document_start(self):
        # The reader is a full document navigation; the mask must pick up the pending
        # text the instant it is created, not only at DOMContentLoaded.
        self.assertIn("function readPendingLoading", self.js)
        match = re.search(r"function ensureBootMask\(\) \{(?:.|\n)*?readPendingLoading\(\)", self.js)
        self.assertIsNotNone(match, "ensureBootMask must read the pending loading state")

    def test_slow_loading_keeps_one_heading_and_only_reveals_actions(self):
        # No mid-flight copy swap to a different loading screen.
        self.assertNotIn("'加载时间较长'", self.js)
        self.assertIn("wr-hh-load-slow", self.js)

    def test_head_stall_guard_reloads_once(self):
        self.assertIn("function guardHeadStall", self.js)
        self.assertIn("wr-hh-head-stall-", self.js)
        self.assertIn("window.location.reload()", self.js)

    def test_slow_loading_retry_forces_document_navigation(self):
        # A failed target may be the current path. go() skips same-path
        # navigation, so retry must always assign the stored href.
        self.assertIn("window.location.assign(loadingState.href);", self.js)
        self.assertNotIn("else { var href = loadingState.href; go(href); }", self.js)

    def test_reader_focus_scan_avoids_the_generic_selector_sweep(self):
        # Opening a book must not run the expensive [class*="card"]/[class*="item"]
        # sweep over the whole reader DOM.
        self.assertIn(
            "else if (isReader()) raw = document.querySelectorAll('.chapterContentError .retry,.readerError button');",
            self.js,
        )

    def test_shell_preconnects_to_reader_asset_hosts(self):
        self.assertIn("rel', 'preconnect'", self.js)
        self.assertIn("cdn.weread.qq.com", self.js)


if __name__ == "__main__":
    unittest.main()