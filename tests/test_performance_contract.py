import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class PerformanceContractTests(unittest.TestCase):
    def test_chrome_keeps_renderer_budget_and_back_forward_cache(self):
        script = (ROOT / "launcher/node.sh").read_text(encoding="utf-8")
        self.assertNotIn("--renderer-process-limit=1", script)
        self.assertNotIn("BackForwardCache", script)
        self.assertRegex(script, r"--renderer-process-limit=2")

    def test_shell_defers_non_reader_offscreen_work(self):
        css = (ROOT / "extension/shell.css").read_text(encoding="utf-8")
        self.assertIn("content-visibility: auto", css)
        self.assertIn("wr-hh-perf", css)
        self.assertNotIn(".readerChapterContent { content-visibility", css)
        self.assertNotIn(".preRenderContent { content-visibility", css)

    def test_focus_sweep_backs_off_while_idle(self):
        js = (ROOT / "extension/content.js").read_text(encoding="utf-8")
        self.assertIn("var focusSweepTimer = null, lastActivityAt = Date.now();", js)
        self.assertIn("var idle = Date.now() - lastActivityAt > 6000;", js)
        self.assertIn("idle ? 4000 : 900", js)
        self.assertIn("document.addEventListener('keydown', markActivity, true);", js)

    def test_shell_guards_share_one_low_frequency_loop(self):
        script = (ROOT / "launcher/node.sh").read_text(encoding="utf-8")
        self.assertIn("shell_guard()", script)
        self.assertNotIn("watchdog()", script)
        self.assertNotIn("focusguard()", script)
        self.assertNotIn("fullguard()", script)
        self.assertIn("sleep 5", script)
        self.assertIn('python3 "$WINDOW_GUARD" focus', script)
        self.assertIn('python3 "$WINDOW_GUARD" fullscreen', script)

    def test_shell_avoids_route_entry_animation(self):
        css = (ROOT / "extension/shell.css").read_text(encoding="utf-8")
        self.assertNotIn("@keyframes wr-hh-arrive", css)
        self.assertNotIn("animation: wr-hh-arrive", css)
    def test_reader_only_reanchors_open_overlays(self):
        js = (ROOT / "extension/content.js").read_text(encoding="utf-8")
        self.assertIn("if (isReader()) {", js)
        self.assertIn("var readerPanel = !menuEl() && !kbdVisible() ? openPanel() : null;", js)
        self.assertIn("return;", js)

    def test_telemetry_blocking_is_declared_and_limited_to_reporting_requests(self):
        manifest = json.loads((ROOT / "extension/manifest.json").read_text(encoding="utf-8"))
        self.assertIn("declarativeNetRequest", manifest["permissions"])
        resources = manifest["declarative_net_request"]["rule_resources"]
        self.assertEqual(resources[0]["path"], "telemetry-rules.json")
        rules = json.loads((ROOT / "extension/telemetry-rules.json").read_text(encoding="utf-8"))
        filters = [rule["condition"]["urlFilter"] for rule in rules]
        self.assertIn("||weread.qq.com/i/hera/chlog", filters)
        self.assertIn("||oss.weread.qq.com/river/single", filters)
        for rule in rules:
            if rule["action"]["type"] != "block":
                continue
            self.assertNotIn("script", rule["condition"]["resourceTypes"])
            self.assertNotIn("sub_frame", rule["condition"]["resourceTypes"])
            self.assertNotIn("main_frame", rule["condition"]["resourceTypes"])
            self.assertNotIn("stylesheet", rule["condition"]["resourceTypes"])
            self.assertNotIn("font", rule["condition"]["resourceTypes"])

    def test_reader_loading_does_not_rebuild_shell_state_on_site_mutations(self):
        js = (ROOT / "extension/content.js").read_text(encoding="utf-8")
        self.assertIn("if (isReader() && loadingState) return;", js)

    def test_telemetry_rule_is_deployed_with_the_extension(self):
        deploy = (ROOT / "tests/deploy.py").read_text(encoding="utf-8")
        install = (ROOT / "ports/install.sh").read_text(encoding="utf-8")
        self.assertIn("extension/telemetry-rules.json", deploy)
        self.assertIn("telemetry-rules.json", install)

    def test_reader_font_is_cached_instead_of_revalidated(self):
        rules = json.loads((ROOT / "extension/telemetry-rules.json").read_text(encoding="utf-8"))
        headers = [rule for rule in rules if rule["action"]["type"] == "modifyHeaders"]
        font_rules = [rule for rule in headers if "SourceHanSerif" in rule["condition"]["urlFilter"]]
        self.assertEqual(len(font_rules), 1)
        response_headers = font_rules[0]["action"]["responseHeaders"]
        self.assertEqual(response_headers[0]["header"], "cache-control")
        self.assertIn("max-age=86400", response_headers[0]["value"])
        self.assertNotIn("main_frame", font_rules[0]["condition"]["resourceTypes"])
        self.assertNotIn("stylesheet", font_rules[0]["condition"]["resourceTypes"])

if __name__ == "__main__":
    unittest.main()
