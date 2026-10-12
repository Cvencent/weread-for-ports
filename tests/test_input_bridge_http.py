"""The reader input bridge must serve requests and keep its allowlist.

input_bridge.py turns gamepad actions into real browser input over a local
HTTP endpoint the MV3 worker talks to. This exercises the HTTP layer with a
stubbed CDP client so it can run without a browser or a device.
"""
import importlib.util
import json
import pathlib
import shutil
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request


ROOT = pathlib.Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "launcher/input_bridge.py"

STUB_CDP = '''
def pick_page_target():
    return {"url": "https://weread.qq.com/web/reader/x",
            "webSocketDebuggerUrl": "ws://127.0.0.1:1/x"}


class WS:
    def __init__(self, *args, **kwargs):
        pass

    def call(self, *args, **kwargs):
        return {"result": {"result": {"value": {"x": 1, "y": 2}}}}

    def close(self):
        pass
'''


def load_bridge():
    """Import input_bridge.py with a stub cdp module beside it."""
    directory = tempfile.mkdtemp()
    (pathlib.Path(directory) / "cdp.py").write_text(STUB_CDP, encoding="utf-8")
    local = pathlib.Path(directory) / "input_bridge.py"
    shutil.copy(BRIDGE, local)
    spec = importlib.util.spec_from_file_location("input_bridge_under_test", local)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class InputBridgeHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bridge = load_bridge()
        cls.server = cls.bridge.Server(("127.0.0.1", 0), cls.bridge.Handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.2)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def post(self, body, header="v8", path="/action"):
        request = urllib.request.Request(
            "http://127.0.0.1:%d%s" % (self.port, path), data=body, method="POST")
        if header is not None:
            request.add_header("X-Weread-Input", header)
            request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read().decode())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read().decode())

    def test_allowed_actions_are_accepted(self):
        for action in self.bridge.SELECTORS:
            status, result = self.post(json.dumps({"action": action}).encode())
            self.assertEqual((status, result), (200, {"ok": True}), action)

    def test_requests_without_the_shared_secret_are_rejected(self):
        status, result = self.post(json.dumps({"action": "catalog"}).encode(), header="nope")
        self.assertEqual((status, result), (400, {"ok": False}))

    def test_unknown_actions_and_paths_are_rejected(self):
        self.assertEqual(self.post(json.dumps({"action": "rm -rf"}).encode()), (400, {"ok": False}))
        self.assertEqual(self.post(json.dumps({"action": "catalog"}).encode(), path="/x"), (400, {"ok": False}))

    def test_oversized_and_empty_bodies_are_rejected(self):
        self.assertEqual(self.post(b""), (400, {"ok": False}))
        self.assertEqual(self.post(b'{"action":"' + b"a" * 200 + b'"}'), (400, {"ok": False}))

    def test_server_is_threaded_and_reusable(self):
        # A blocked request must not stop the next one from being served.
        self.assertTrue(getattr(self.bridge.Server, "daemon_threads", False))
        self.assertTrue(getattr(self.bridge.Server, "allow_reuse_address", False))

    def test_cleanup_cannot_raise_over_the_original_error(self):
        source = BRIDGE.read_text(encoding="utf-8")
        cleanup = source.split("    finally:", 1)[1].split("class Handler", 1)[0]
        self.assertIn("try:", cleanup)
        self.assertIn("except (OSError, ValueError, KeyError, RuntimeError):", cleanup)


if __name__ == "__main__":
    unittest.main()
