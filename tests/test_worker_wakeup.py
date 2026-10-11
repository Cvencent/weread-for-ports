"""The MV3 worker must answer the document warm-up message.

content.js sends {"action": "wake"} once per document so the service worker is
already resident when the first reader action arrives. The action allowlist
used to reject "wake" before the handler could answer it, which left the
worker cold: the first X/A in the reader then paid a full worker start plus a
bridge round trip, showing up as a key press that did nothing.

These tests execute background-v8.1.js against a stub chrome.runtime.
"""
import pathlib
import re
import shutil
import subprocess
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
HARNESS = pathlib.Path(__file__).resolve().parent / "_worker_wake.js"

QUOTED = re.compile("[\"']([^\"']+)[\"']")


class WorkerWarmupTests(unittest.TestCase):
    def run_harness(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not available")
        return subprocess.run([node, str(HARNESS)], capture_output=True, text=True)

    def test_wakeup_message_is_answered_without_touching_the_bridge(self):
        result = self.run_harness()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("WORKER: PASS", result.stdout)
        self.assertIn("wake is answered", result.stdout)
        self.assertIn("wake performs no HTTP request", result.stdout)
        self.assertNotIn("BAD", result.stdout)

    def test_wakeup_is_in_the_action_allowlist(self):
        source = (ROOT / "extension/background-v8.1.js").read_text(encoding="utf-8")
        allowlist = re.search(r"\[(.+?)\]\.includes\(message\.action\)", source, re.S)
        self.assertIsNotNone(allowlist, "worker no longer filters actions")
        actions = QUOTED.findall(allowlist.group(1))
        self.assertIn("wake", actions)
        for action in ("catalog", "settings", "activate", "close",
                       "font-previous", "font-next", "annotation"):
            self.assertIn(action, actions)

    def test_wakeup_never_reaches_the_local_bridge(self):
        # input_bridge.py has no "wake" selector, so forwarding it would be a
        # guaranteed 400 on every document load.
        bridge = (ROOT / "launcher/input_bridge.py").read_text(encoding="utf-8")
        selectors = re.search(r"SELECTORS = \{(.*?)\n\}", bridge, re.S).group(1)
        self.assertNotIn("wake", selectors)


if __name__ == "__main__":
    unittest.main()
