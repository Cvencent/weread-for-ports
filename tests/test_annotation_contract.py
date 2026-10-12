"""Contracts for selecting underlined reader comments with the left stick."""
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class AnnotationContractTests(unittest.TestCase):
    def setUp(self):
        self.gptk = (ROOT / "launcher/weread.gptk").read_text(encoding="utf-8")
        self.js = (ROOT / "extension/content.js").read_text(encoding="utf-8")
        self.css = (ROOT / "extension/shell.css").read_text(encoding="utf-8")
        self.background = (ROOT / "extension/background-v8.1.js").read_text(encoding="utf-8")
        self.bridge = (ROOT / "launcher/input_bridge.py").read_text(encoding="utf-8")

    def test_left_stick_maps_to_annotation_previous_and_next(self):
        for direction in ("up", "left"):
            self.assertIn(f"left_analog_{direction} = insert", self.gptk)
        for direction in ("down", "right"):
            self.assertIn(f"left_analog_{direction} = delete", self.gptk)

    def test_reader_selects_visible_underlines_in_visual_order(self):
        self.assertIn(".wr_underline_wrapper", self.js)
        self.assertIn("function annotationItems()", self.js)
        self.assertIn("var raw = $$('.wr_underline_wrapper');", self.js)
        self.assertNotIn("var raw = $('.wr_underline_wrapper');", self.js)
        self.assertNotIn("var old = $('[data-wr-hh-annotation]');", self.js)
        self.assertNotIn("var old = $('.wr-hh-annotation');", self.js)
        self.assertIn("function selectAnnotation(step)", self.js)
        self.assertIn("annotationEl", self.js)
        self.assertIn("wr-hh-annotation", self.css)
        self.assertIn("outline:", self.css)

    def test_first_stick_move_selects_the_first_visible_annotation(self):
        self.assertIn("if (at < 0) at = 0;", self.js)

    def test_launcher_deploys_the_updated_stick_mapping(self):
        deploy = (ROOT / "tests/deploy.py").read_text(encoding="utf-8")
        final_state = (ROOT / "tests/final_state.py").read_text(encoding="utf-8")
        remote = '"/storage/roms/ports/weread/weread.gptk"'
        self.assertIn('"launcher/weread.gptk": ' + remote, deploy)
        self.assertIn('"launcher/weread.gptk": ' + remote, final_state)

    def test_annotation_click_can_use_a_point_inside_the_selected_underline(self):
        self.assertIn("el.contains(hit)||hit.contains(el)", self.bridge)

    def test_annotation_click_prefers_the_site_native_handler(self):
        self.assertIn("annotationEl.click();", self.js)
        self.assertIn("readerInput('annotation')", self.js)
    def test_b_closes_the_review_panel_with_its_native_close_button(self):
        self.assertIn("reader_float_panel_header_closeBtn", self.js)
        self.assertIn("clickFloatPanelClose", self.js)
        self.assertIn('data-wr-hh-annotation-label', self.js)
    def test_a_opens_the_selected_annotation_through_trusted_input(self):
        self.assertIn("readerInput('annotation')", self.js)
        self.assertIn("'annotation'", self.background)
        self.assertIn('"annotation": "[data-wr-hh-annotation]"', self.bridge)

    def test_font_change_success_is_not_reported_as_failure(self):
        self.assertIn("beforeFontLevel", self.js)
        self.assertIn("afterFontLevel[1] !== beforeFontLevel", self.js)

    def test_cold_service_worker_message_is_retried(self):
        self.assertIn("message port closed", self.js)
        self.assertIn("function send(attempt)", self.js)
        self.assertIn("attempt < 2", self.js)
        self.assertIn("action: 'wake'", self.js)
        self.assertIn("message.action === 'wake'", self.background)


if __name__ == "__main__":
    unittest.main()
