"""Contracts for the short-lived reader setting busy overlay."""
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class ReaderBusyContractTests(unittest.TestCase):
    def setUp(self):
        self.js = (ROOT / "extension/content.js").read_text(encoding="utf-8")
        self.css = (ROOT / "extension/shell.css").read_text(encoding="utf-8")

    def test_busy_overlay_is_independent_from_navigation_loading(self):
        self.assertIn("id = 'wr-hh-busy'", self.js)
        self.assertIn("#wr-hh-busy { position: fixed", self.css)
        self.assertIn(".wr-hh-spinner", self.css)
        busy_source = self.js.split("function beginReaderBusy", 1)[1].split("function finishReaderBusy", 1)[0]
        self.assertNotIn("el.id = 'wr-hh-loading'", busy_source)

    def test_every_slow_reader_action_has_a_busy_label(self):
        for action in ("font-previous", "font-next", "activate", "catalog", "settings", "close", "annotation"):
            self.assertIn("'" + action + "':", self.js)
        self.assertIn("正在切换字体", self.js)
        self.assertIn("正在调整字号", self.js)
        self.assertIn("正在打开阅读设置", self.js)
        self.assertIn("正在打开评论", self.js)

    def test_busy_state_locks_reader_controls_until_it_finishes(self):
        self.assertIn("readerBusyState", self.js)
        self.assertRegex(
            self.js,
            r"readerBusyState.*\n.*ArrowUp\|ArrowDown\|ArrowLeft\|ArrowRight",
        )
        self.assertIn("Home|End", self.js)
        self.assertIn("e.preventDefault(); e.stopPropagation(); return;", self.js)

    def test_completion_uses_reader_state_not_a_fixed_sleep(self):
        self.assertIn("function readerBusyComplete", self.js)
        self.assertIn("busyContext", self.js)
        self.assertIn("wr_reader_font_size_level_", self.js)
        self.assertIn("panel.querySelector('.font-panel-content')", self.js)
        self.assertIn("p.matches('.readerCatalog')", self.js)
        self.assertIn("selectionSignature", self.js)

    def test_busy_overlay_has_minimum_and_timeout_bounds(self):
        self.assertIn("elapsed < 200", self.js)
        self.assertIn("elapsed >= 5000", self.js)
        self.assertIn("操作未完成，请重试", self.js)

    def test_native_close_and_annotation_paths_start_busy(self):
        close_block = self.js.split("function clickFloatPanelClose", 1)[1].split("function openAnnotation", 1)[0]
        annotation_block = self.js.split("function openAnnotation", 1)[1].split("function pageBtn", 1)[0]
        self.assertIn("beginReaderBusy('close')", close_block)
        self.assertIn("watchReaderBusy('close'", close_block)
        self.assertIn("beginReaderBusy('annotation')", annotation_block)
