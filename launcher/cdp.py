#!/usr/bin/env python3
"""Minimal dependency-free Chrome DevTools Protocol client for the handheld.

This module is a hard runtime dependency of the shell:

* ``launcher/input_bridge.py`` imports it to turn gamepad actions into real
  browser input (catalog, settings, font size, annotations).
* ``launcher/node.sh`` runs it as a script to pull a dead page back home.

It only uses the standard library because the handheld ships Python without
pip. Keep this file installed next to the other launcher files.

Command line usage:
    python3 cdp.py "<javascript>"      evaluate JavaScript and print the result
    python3 cdp.py --url <url>        navigate first, then evaluate
"""
import base64
import hashlib
import json
import os
import re
import socket
import struct
import sys
import urllib.request

HOST = "127.0.0.1"
PORT = 9222
_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def http_json(path):
    with urllib.request.urlopen(f"http://{HOST}:{PORT}{path}", timeout=15) as response:
        return json.loads(response.read().decode("utf-8", "replace"))


def pick_page_target():
    """Return the WeRead page target, falling back to the only other page."""
    targets = http_json("/json")
    pages = [target for target in targets if target.get("type") == "page"]
    if not pages:
        raise RuntimeError("no page target")
    for target in pages:
        if "weread.qq.com" in target.get("url", ""):
            return target
    return pages[0]


class WS:
    """Tiny text-frame WebSocket client; enough for one request at a time."""

    def __init__(self, url):
        match = re.match(r"ws://([^:/]+):(\d+)(/.*)", url)
        if not match:
            raise ValueError("unsupported websocket url")
        host, port, path = match.group(1), int(match.group(2)), match.group(3)
        self.sock = socket.create_connection((host, port), timeout=30)
        key = base64.b64encode(os.urandom(16)).decode()
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(request.encode())
        buffer = b""
        while b"\r\n\r\n" not in buffer:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise IOError("closed during handshake")
            buffer += chunk
        expected = base64.b64encode(
            hashlib.sha1((key + _WS_GUID).encode()).digest()
        ).decode()
        if expected not in buffer.decode("utf-8", "replace"):
            raise RuntimeError("handshake failed")

    def send(self, text):
        self._send_frame(0x1, text.encode("utf-8"))

    def _read(self, count):
        buffer = b""
        while len(buffer) < count:
            chunk = self.sock.recv(count - len(buffer))
            if not chunk:
                raise IOError("closed")
            buffer += chunk
        return buffer

    def _send_frame(self, opcode, payload):
        header = bytearray([0x80 | opcode])
        size = len(payload)
        if size < 126:
            header.append(0x80 | size)
        elif size < 65536:
            header.append(0x80 | 126)
            header += struct.pack(">H", size)
        else:
            header.append(0x80 | 127)
            header += struct.pack(">Q", size)
        mask = os.urandom(4)
        header += mask
        self.sock.sendall(bytes(header)
                          + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

    def recv(self):
        """Read one complete application message.

        A single frame is not one message. Chrome splits large
        Runtime.evaluate results across continuation frames and sends ping
        frames on its own timer, so a parser that reads one frame and decodes it
        as JSON corrupts or stalls on payloads that occur in normal use.
        Continuation frames are reassembled, and control frames are handled
        in-line: ping is answered with a pong carrying the same payload, and
        pong is ignored.
        """
        chunks = []
        started = False
        while True:
            header = self._read(2)
            fin = bool(header[0] & 0x80)
            opcode = header[0] & 0x0F
            length = header[1] & 0x7F
            if length == 126:
                length = struct.unpack(">H", self._read(2))[0]
            elif length == 127:
                length = struct.unpack(">Q", self._read(8))[0]
            masked = bool(header[1] & 0x80)
            mask = self._read(4) if masked else None
            payload = self._read(length) if length else b""
            if mask:
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))

            if opcode == 0x8:
                raise IOError("ws closed")
            if opcode == 0x9:
                self._send_frame(0xA, payload)
                continue
            if opcode == 0xA:
                continue
            if opcode == 0x0:
                if not started:
                    raise IOError("continuation without a start frame")
                chunks.append(payload)
            elif opcode in (0x1, 0x2):
                if started:
                    raise IOError("new data frame inside a fragmented message")
                chunks = [payload]
                started = True
            else:
                raise IOError("unsupported opcode %d" % opcode)

            if fin:
                return b"".join(chunks).decode("utf-8", "replace")

    def call(self, mid, method, params=None):
        self.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            message = json.loads(self.recv())
            if message.get("id") == mid:
                return message

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2

    navigate = None
    if args[0] == "--url":
        navigate = args[1]
        args = args[2:]
    expression = args[0] if args else "1"

    target = pick_page_target()
    connection = WS(target["webSocketDebuggerUrl"])
    try:
        mid = 1
        if navigate:
            connection.call(mid, "Page.enable")
            mid += 1
            connection.call(mid, "Page.navigate", {"url": navigate})
            mid += 1
            import time
            time.sleep(12)

        response = connection.call(mid, "Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True,
        })
        result = response.get("result", {})
        if "exceptionDetails" in result:
            print("JS-ERROR:", json.dumps(result["exceptionDetails"], ensure_ascii=False)[:800])
        value = result.get("result", {}).get("value")
        if isinstance(value, (dict, list)):
            print(json.dumps(value, ensure_ascii=False, indent=1))
        else:
            print(value)
    finally:
        connection.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
