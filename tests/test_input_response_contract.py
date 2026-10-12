"""The MV3 worker and the reader's input guard must always come back.

Two separate ways a reader key press could be swallowed forever:

1. background-v8.1.js relied on aborting the fetch to end the request. A fetch
   that ignores the abort signal left respond() uncalled, so content.js's
   sendMessage callback never ran.
2. readerInput() clears readerInputPending only inside that callback, and
   readerInputPending gates every reader key, so one lost reply wedged the
   reader for the life of the document.

Both sides now enforce their own deadline. These tests execute the real
JavaScript against stub chrome.runtime, so removing either guard fails here.
"""
import pathlib
import shutil
import subprocess
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
ABORT_HARNESS = pathlib.Path(__file__).resolve().parent / "_worker_abort.js"
GUARD_HARNESS = pathlib.Path(__file__).resolve().parent / "_reader_input_guard.js"

WORKER = (ROOT / "extension/background-v8.1.js").read_text(encoding="utf-8")
CONTENT = (ROOT / "extension/content.js").read_text(encoding="utf-8")


def run_harness(path, timeout=120):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("node is not available")
    # The harness prints the user-facing Chinese hint, which the default Windows
    # codec cannot decode, so read the bytes and decode explicitly.
    proc = subprocess.run([node, str(path)], capture_output=True, timeout=timeout)
    return subprocess.CompletedProcess(
        proc.args, proc.returncode,
        proc.stdout.decode("utf-8", "replace"),
        proc.stderr.decode("utf-8", "replace"),
    )


class WorkerResponseContractTests(unittest.TestCase):
    def setUp(self):
        self.result = run_harness(ABORT_HARNESS)

    def test_worker_abort_contract_holds(self):
        self.assertEqual(self.result.returncode, 0, self.result.stdout + self.result.stderr)
        self.assertIn("ABORT: PASS", self.result.stdout)
        self.assertNotIn("BAD", self.result.stdout)

    def test_worker_enforces_its_own_deadline(self):
        # The abort signal alone cannot guarantee respond() runs, so the worker
        # races the request against a timer it controls.
        self.assertIn("Promise.race([request, deadline])", WORKER)
        self.assertIn("if (settled) return;", WORKER)

    def test_worker_timeout_error_is_one_content_js_retries(self):
        # Chrome's abort text ("This operation was aborted") is not in
        # content.js's retry set, so a hung bridge would have surfaced as
        # "操作未完成，请重试" instead of being retried.
        self.assertIn("Input service unavailable", WORKER)
        retry_block = CONTENT.split("function send(attempt) {", 1)[1].split("\n    }", 1)[0]
        self.assertIn("input service unavailable", retry_block.lower())


class ReaderInputGuardTests(unittest.TestCase):
    def setUp(self):
        self.result = run_harness(GUARD_HARNESS)

    def test_reader_releases_its_reentry_guard(self):
        self.assertEqual(self.result.returncode, 0, self.result.stdout + self.result.stderr)
        self.assertIn("GUARD: PASS", self.result.stdout)
        self.assertNotIn("BAD", self.result.stdout)

    def test_guard_clears_the_timeout_holder(self):
        self.assertIn("clearTimeout(attemptState.timer)", CONTENT)
        self.assertIn("if (attemptState.done) return;", CONTENT)

    def test_guard_budget_clears_the_slowest_legitimate_retry_chain(self):
        # 3 worker budgets plus the 450ms and 1200ms backoffs. A guard below
        # this would cancel a retry that was about to succeed.
        import re

        match = re.search(r"attemptState\.timer = setTimeout\(function \(\) \{[\s\S]*?\}, (\d+)\);",
                          CONTENT)
        self.assertIsNotNone(match, "the reader-side guard timer disappeared")
        budget = int(match.group(1))
        self.assertGreater(budget, 3 * 4000 + 450 + 1200)


if __name__ == "__main__":
    unittest.main()