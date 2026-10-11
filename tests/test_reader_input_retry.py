"""The reader input path must survive a bridge that is not ready yet.

node.sh starts input_bridge.py before the browser, so for the first seconds of a
cold launch the local bridge answers with an error (no page target to drive
yet). background-v8.1.js turns any non-2xx into "Input service unavailable", and
content.js only retried on worker-cold messages, so the very first X/A in the
reader was reported to the user as "操作未完成，请重试" instead of being retried.
"""
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
JS = (ROOT / "extension/content.js").read_text(encoding="utf-8")
WORKER = (ROOT / "extension/background-v8.1.js").read_text(encoding="utf-8")
BRIDGE = (ROOT / "launcher/input_bridge.py").read_text(encoding="utf-8")


class ReaderInputRetryTests(unittest.TestCase):
    def retry_block(self):
        return re.search(r"function send\(attempt\) \{(.*?)\n    \}", JS, re.S).group(1)

    def test_bridge_not_listening_is_retried(self):
        block = self.retry_block()
        self.assertIn("attempt < 2", block)
        # The worker reports any non-2xx from the bridge as this message.
        self.assertIn("Input service unavailable", WORKER)
        self.assertIn("input service unavailable", block.lower())

    def test_cold_worker_is_still_retried(self):
        block = self.retry_block()
        self.assertIn("message port closed", block)
        self.assertIn("service worker", block.lower())

    def test_retry_uses_backoff_not_a_hot_loop(self):
        block = self.retry_block()
        self.assertIn("attempt === 0 ? 450 : 1200", block)

    def test_bridge_reports_a_missing_page_target_as_a_plain_error(self):
        # click_action raises when pick_page_target() finds nothing, and the
        # handler turns that into 400 {ok: false} with no error field. That is
        # what the worker converts into "Input service unavailable".
        self.assertIn("raise RuntimeError(\"no page target\")",
                      (ROOT / "launcher/cdp.py").read_text(encoding="utf-8"))
        self.assertIn("target = cdp.pick_page_target()", BRIDGE)
        self.assertIn("status, result = 400, {\"ok\": False}", BRIDGE)

    def test_worker_reports_bridge_failures_without_leaking_detail(self):
        self.assertIn("if (!response.ok) throw new Error('Input service unavailable');", WORKER)
        self.assertIn("respond({ ok: false, error: error.message })", WORKER)


if __name__ == "__main__":
    unittest.main()
