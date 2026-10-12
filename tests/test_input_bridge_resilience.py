"""The bridge must always answer, and must never pin a thread.

input_bridge.py is the only thing standing between a gamepad press and the
browser. Two failure modes made it drop the connection instead of replying:

  * do_POST() named four exception types. Anything else -- a TypeError out of a
    CDP payload, an IndexError out of a decoded structure -- escaped the handler
    and BaseHTTPRequestHandler dropped the socket without a response, so the
    worker saw a network error instead of a rejection.
  * Content-Length was trusted. A peer that promised more bytes than it sent
    left rfile.read(length) blocked indefinitely, holding one of the server's
    threads; the server is ThreadingHTTPServer, so those threads accumulate.

Both are covered here by driving the real handler over a real socket.
"""
import importlib.util
import pathlib
import shutil
import socket
import tempfile
import threading
import unittest
import urllib.error
import urllib.request


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_bridge(cdp_source):
    directory = tempfile.mkdtemp()
    (pathlib.Path(directory) / "cdp.py").write_text(cdp_source, encoding="utf-8")
    local = pathlib.Path(directory) / "input_bridge.py"
    shutil.copy(ROOT / "launcher" / "input_bridge.py", local)
    spec = importlib.util.spec_from_file_location("input_bridge_under_test", local)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HANGING_CDP = """
class WS:
    def __init__(self, url): pass
    def call(self, mid, method, params=None):
        raise ZeroDivisionError("a type nobody thought to list")
    def close(self): pass
def pick_page_target():
    return {"url": "https://weread.qq.com/web/reader/x",
            "webSocketDebuggerUrl": "ws://127.0.0.1:1/x"}
"""

WORKING_CDP = """
import time
class WS:
    def __init__(self, url): pass
    def call(self, mid, method, params=None):
        time.sleep(0.02)
        return {"result": {"result": {"value": {"x": 10, "y": 10}}}}
    def close(self): pass
def pick_page_target():
    return {"url": "https://weread.qq.com/web/reader/x",
            "webSocketDebuggerUrl": "ws://127.0.0.1:1/x"}
"""


class BridgeServerCase(unittest.TestCase):
    cdp_source = WORKING_CDP

    def setUp(self):
        self.bridge = load_bridge(self.cdp_source)
        self.server = self.bridge.Server(("127.0.0.1", 0), self.bridge.Handler)
        self.port = self.server.server_address[1]
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.server_close)

    def post(self, body, headers=None, timeout=20):
        request = urllib.request.Request(
            "http://127.0.0.1:%d/action" % self.port, data=body,
            headers=headers or {"Content-Type": "application/json",
                                "X-Weread-Input": "v8"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.status, response.read().decode()
        except urllib.error.HTTPError as error:
            return error.code, error.read().decode()


class UnexpectedFailureTests(BridgeServerCase):
    cdp_source = HANGING_CDP

    def test_an_unlisted_exception_still_produces_a_response(self):
        status, body = self.post(b'{"action":"catalog"}')
        self.assertEqual(status, 400)
        self.assertIn('"ok": false', body)

    def test_the_bridge_keeps_serving_after_an_unlisted_exception(self):
        # A dropped connection is worse than a rejected one: the worker retries
        # a network error but a refused request is a final answer.
        for action in (b"catalog", b"close", b"font-next"):
            status, body = self.post(b'{"action":"' + action + b'"}')
            self.assertEqual(status, 400, action)
            self.assertIn('"ok": false', body, action)


class NormalTrafficTests(BridgeServerCase):
    def test_a_working_bridge_still_returns_ok(self):
        status, body = self.post(b'{"action":"catalog"}')
        self.assertEqual(status, 200)
        self.assertIn('"ok": true', body)

    def test_the_malformed_request_contracts_are_unchanged(self):
        for body, expected in ((b'{"action":"rm -rf"}', 400),
                               (b'{}', 400),
                               (b'{', 400),
                               (b'{"action":"catalog"}', 200)):
            status, _ = self.post(body)
            self.assertEqual(status, expected, body)
        # Missing or wrong header.
        status, _ = self.post(b'{"action":"catalog"}',
                              headers={"Content-Type": "application/json"})
        self.assertEqual(status, 400)
        # Wrong path: the handler only implements do_POST, so a POST to another
        # path is declined rather than acted on.
        request = urllib.request.Request(
            "http://127.0.0.1:%d/other" % self.port, data=b'{"action":"catalog"}',
            headers={"X-Weread-Input": "v8"})
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                self.fail("expected a rejection, got %s" % response.status)
        except urllib.error.HTTPError as error:
            self.assertNotEqual(error.code, 200)

    def test_concurrent_actions_are_all_served(self):
        results = {}

        def run(index):
            action = (b"catalog", b"settings", b"font-next", b"close")[index % 4]
            results[index] = self.post(b'{"action":"' + action + b'"}')

        threads = [threading.Thread(target=run, args=(i,)) for i in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        self.assertEqual(len(results), 8)
        for status, body in results.values():
            self.assertEqual(status, 200)
            self.assertIn('"ok": true', body)


class StalledPeerTests(unittest.TestCase):
    """A peer that under-delivers must not hold a thread forever."""

    def test_a_short_body_is_bounded_and_answered(self):
        bridge = load_bridge(HANGING_CDP)
        server = bridge.Server(("127.0.0.1", 0), bridge.Handler)
        port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)

        connection = socket.create_connection(("127.0.0.1", port), timeout=10)
        self.addCleanup(connection.close)
        # Promises 100 bytes, sends 19, then says nothing more.
        connection.sendall(b"POST /action HTTP/1.1\r\nHost: x\r\n"
                           b"X-Weread-Input: v8\r\nContent-Length: 100\r\n\r\n"
                           b'{"action":"catalog"}')
        connection.settimeout(30)
        try:
            data = connection.recv(4096)
        except socket.timeout:
            self.fail("the handler never answered; rfile.read() waited forever")
        self.assertIn(b"400", data.split(b"\r\n", 1)[0])

    def test_the_handler_bounds_its_socket(self):
        bridge = load_bridge(HANGING_CDP)
        self.assertGreater(bridge.Handler.timeout, 0)
        self.assertLessEqual(bridge.Handler.timeout, 15,
                             "a generous bound is fine, an unbounded one is not")


if __name__ == "__main__":
    unittest.main()