"""cdp.WS must handle the frame shapes Chrome actually sends.

launcher/cdp.py is a hand-rolled WebSocket client and a hard runtime
dependency: input_bridge.py imports it for every gamepad action, and node.sh
runs it to recover a dead page. Three defects lived in its frame parser, all
reachable in normal use:

  * Chrome splits large Runtime.evaluate results across continuation frames.
    The old parser read one frame and decoded it as JSON, so a big result was a
    JSONDecodeError and the action reported failure to the user.
  * Chrome sends ping frames on its own timer. The old parser fed the ping
    payload to json.loads, which threw, and it never sent the pong the protocol
    requires, so the server was entitled to drop the connection.
  * A ping arriving between two replies was returned as if it were the reply,
    so call() could hand back the wrong message.

A close frame must still abort the call. That is correct behaviour, not a
defect.

The fake server drains the client's frames in a background thread and stays up
until the client goes away. Both details matter: a server that only sends lets
the client's pong pile up in the socket buffer until its next send fails, and
one that closes early loses a late pong. Either shows up as an intermittent
"closed" that has nothing to do with the code under test.
"""
import base64
import hashlib
import importlib.util
import json
import pathlib
import socket
import struct
import threading
import unittest

REPO = str(pathlib.Path(__file__).resolve().parents[1])

_spec = importlib.util.spec_from_file_location("cdp", REPO + r"\launcher\cdp.py")
cdp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cdp)

MSG = '{"id":1,"result":{"result":{"value":"ok"}}}'
BIG = json.dumps({"id": 1, "result": {"result": {"value": "x" * 40000}}})


def frame(payload, opcode=0x1, fin=True):
    """Build one unmasked server->client frame."""
    data = payload.encode() if isinstance(payload, str) else payload
    header = bytearray([(0x80 if fin else 0x00) | opcode])
    size = len(data)
    if size < 126:
        header.append(size)
    elif size < 65536:
        header.append(126)
        header += struct.pack(">H", size)
    else:
        header.append(127)
        header += struct.pack(">Q", size)
    return bytes(header) + data


def masked_frame(payload, opcode=0x1):
    """Build one masked frame, which a client must still be able to read."""
    data = payload.encode() if isinstance(payload, str) else payload
    mask = b"\x01\x02\x03\x04"
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    header = bytearray([0x80 | opcode, 0x80 | len(masked)])
    return bytes(header) + mask + masked


def parse_client_frames(raw):
    """Decode every client->server frame in raw. All of them are masked."""
    out = []
    offset = 0
    while offset + 2 <= len(raw):
        opcode = raw[offset] & 0x0F
        length = raw[offset + 1] & 0x7F
        head = 2
        if length == 126:
            length = struct.unpack(">H", raw[offset + 2:offset + 4])[0]
            head = 4
        elif length == 127:
            length = struct.unpack(">Q", raw[offset + 2:offset + 10])[0]
            head = 10
        mask = None
        if raw[offset + 1] & 0x80:
            mask = raw[offset + head:offset + head + 4]
            head += 4
        payload = raw[offset + head:offset + head + length]
        if mask:
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        out.append((opcode, payload))
        offset += head + length
    return out


class FakeServer(threading.Thread):
    """Serve one WebSocket handshake, then the given frames."""

    def __init__(self, script):
        super().__init__(daemon=True)
        self.script = script
        self.received = []
        self._stop = threading.Event()
        self._ready = threading.Event()
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(1)
        self.port = self.sock.getsockname()[1]

    def run(self):
        try:
            conn, _ = self.sock.accept()
        except OSError:
            return
        try:
            self._handshake(conn)
            reader = threading.Thread(target=self._drain, args=(conn,),
                                      daemon=True)
            reader.start()
            for item in self.script:
                try:
                    conn.sendall(item)
                except OSError:
                    break
            # Stay up until the client closes, so a pong written late is not
            # lost and the test does not race the socket shut.
            self._stop.wait(timeout=5)
        finally:
            self._stop.set()
            try:
                conn.close()
            except OSError:
                pass

    def _handshake(self, conn):
        buffer = b""
        while b"\r\n\r\n" not in buffer:
            chunk = conn.recv(4096)
            if not chunk:
                raise IOError("closed during handshake")
            buffer += chunk
        key = ""
        for line in buffer.decode("utf-8", "replace").split("\r\n"):
            if line.lower().startswith("sec-websocket-key:"):
                key = line.split(":", 1)[1].strip()
        accept = base64.b64encode(hashlib.sha1(
            (key + cdp._WS_GUID).encode()).digest()).decode()
        conn.sendall(("HTTP/1.1 101 Switching Protocols\r\n"
                      "Upgrade: websocket\r\nConnection: Upgrade\r\n"
                      "Sec-WebSocket-Accept: " + accept + "\r\n\r\n").encode())

    def _drain(self, conn):
        """Read the client's frames continuously so its buffers never fill."""
        conn.settimeout(0.05)
        while not self._stop.is_set():
            try:
                chunk = conn.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                return
            if not chunk:
                return
            self.received.append(chunk)
            self._ready.set()

    def finish(self):
        """Wait until any pending client frame has been recorded."""
        self._ready.wait(timeout=1)

    def url(self):
        return "ws://127.0.0.1:%d/devtools/page/1" % self.port


def call(script, mid=1):
    """Connect, issue one call, and always release both ends."""
    server = FakeServer(script)
    server.start()
    try:
        ws = cdp.WS(server.url())
    except Exception as exc:
        server._stop.set()
        server.join(timeout=2)
        raise AssertionError("handshake failed: %s" % exc)
    try:
        result = ws.call(mid, "Runtime.evaluate", {"expression": "1"})
    finally:
        ws.close()
        server.finish()
        server._stop.set()
        server.join(timeout=3)
        server.sock.close()
    return result, server


class WebSocketFrameTests(unittest.TestCase):
    def assert_message(self, script, mid=1):
        response, _ = call(script, mid)
        return response

    def test_plain_text_frame(self):
        self.assertEqual(self.assert_message([frame(MSG)])["id"], 1)

    def test_two_fragment_message_is_reassembled(self):
        got = self.assert_message([frame(MSG[:20], fin=False),
                                   frame(MSG[20:], fin=True, opcode=0x0)])
        self.assertEqual(got, json.loads(MSG))

    def test_three_fragment_message_is_reassembled(self):
        got = self.assert_message([frame(MSG[:10], fin=False),
                                   frame(MSG[10:30], fin=False, opcode=0x0),
                                   frame(MSG[30:], fin=True, opcode=0x0)])
        self.assertEqual(got, json.loads(MSG))

    def test_large_result_split_at_the_header_boundary(self):
        """A big evaluate result crosses the 126-byte header boundary, which is
        where Chrome actually fragments."""
        got = self.assert_message([frame(BIG[:200], fin=False),
                                   frame(BIG[200:], fin=True, opcode=0x0)])
        self.assertEqual(len(got["result"]["result"]["value"]), 40000)

    def test_ping_before_the_reply_is_answered_and_skipped(self):
        got = self.assert_message([frame(b"hb", opcode=0x9), frame(MSG)])
        self.assertEqual(got, json.loads(MSG))

    def test_ping_between_two_replies_is_skipped(self):
        got = self.assert_message([frame(b"hb", opcode=0x9), frame(MSG)])
        self.assertEqual(got["id"], 1)

    def test_ping_is_answered_with_a_pong_carrying_the_payload(self):
        _response, server = call([frame(b"keepalive", opcode=0x9), frame(MSG)])
        server.finish()
        pongs = [f for f in parse_client_frames(b"".join(server.received))
                 if f[0] == 0xA]
        self.assertTrue(pongs, "no pong was sent")
        self.assertEqual(pongs[0][1], b"keepalive")

    def test_pong_is_ignored(self):
        self.assertEqual(self.assert_message([frame(b"x", opcode=0xA),
                                              frame(MSG)])["id"], 1)

    def test_binary_frame_payload_is_returned(self):
        self.assertEqual(self.assert_message([frame(MSG.encode(),
                                                   opcode=0x2)])["id"], 1)

    def test_masked_frame_is_unmasked_before_decoding(self):
        self.assertEqual(self.assert_message([masked_frame(MSG)])["id"], 1)

    def test_close_frame_aborts_the_call(self):
        with self.assertRaises(IOError):
            call([frame(b"", opcode=0x8), frame(MSG)])

    def test_continuation_without_a_start_is_rejected(self):
        with self.assertRaises(IOError):
            call([frame(MSG, fin=False, opcode=0x0)])

    def test_call_skips_messages_for_other_ids(self):
        got = self.assert_message([
            frame(json.dumps({"id": 99, "method": "Page.loadEventFired"})),
            frame(MSG)])
        self.assertEqual(got["id"], 1)

    def test_websocket_can_be_used_as_a_context_manager(self):
        """The socket must be released even when the call raises, so a caller
        that handles an error does not leak one descriptor per action."""
        server = FakeServer([frame(MSG)])
        server.start()
        try:
            with cdp.WS(server.url()) as ws:
                self.assertEqual(ws.call(1, "Runtime.evaluate", {})["id"], 1)
        finally:
            server._stop.set()
            server.join(timeout=3)
            server.sock.close()


if __name__ == "__main__":
    unittest.main()
