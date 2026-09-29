"""Chrome/CDP regression for Mermaid's author-controlled request boundary.

The module response is fulfilled through CDP, so this test needs no network.
Its fixed stand-in behaves like the vulnerable Mermaid image-node path in the
two ways that matter here: it tries to load the attacker URL while rendering,
then returns an SVG containing an image. The page CSP must prevent the request,
and the renderer-owned SVG allowlist must reject the result without hiding the
readable source.
"""

import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET

from canvas import render


ATTACKER_URL = "https://example.invalid/canvas-audit.png"
CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    shutil.which("google-chrome"),
    shutil.which("chromium"),
    shutil.which("chromium-browser"),
)


class _PageHandler(BaseHTTPRequestHandler):
    page = b""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(self.page)))
        self.end_headers()
        self.wfile.write(self.page)

    def log_message(self, *args):
        pass


class _WebSocket:
    """The small RFC 6455 subset Chrome's JSON CDP endpoint needs."""

    def __init__(self, url):
        parts = urlsplit(url)
        self.socket = socket.create_connection((parts.hostname, parts.port), timeout=10)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            "GET %s HTTP/1.1\r\nHost: %s:%s\r\nUpgrade: websocket\r\n"
            "Connection: Upgrade\r\nSec-WebSocket-Key: %s\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        ) % (parts.path, parts.hostname, parts.port, key)
        self.socket.sendall(request.encode("ascii"))
        response = b""
        while b"\r\n\r\n" not in response:
            response += self.socket.recv(4096)
        if not response.startswith(b"HTTP/1.1 101"):
            raise RuntimeError("Chrome refused CDP websocket: %r" % response[:200])

    def close(self):
        self.socket.close()

    def _read(self, count):
        data = b""
        while len(data) < count:
            chunk = self.socket.recv(count - len(data))
            if not chunk:
                raise EOFError("Chrome closed the CDP websocket")
            data += chunk
        return data

    def send(self, value):
        payload = json.dumps(value).encode("utf-8")
        mask = os.urandom(4)
        length = len(payload)
        if length < 126:
            header = bytes((0x81, 0x80 | length))
        elif length < 65536:
            header = bytes((0x81, 0xFE)) + struct.pack("!H", length)
        else:
            header = bytes((0x81, 0xFF)) + struct.pack("!Q", length)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        self.socket.sendall(header + mask + masked)

    def receive(self):
        first, second = self._read(2)
        opcode = first & 0x0F
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._read(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._read(8))[0]
        if second & 0x80:
            mask = self._read(4)
        else:
            mask = None
        payload = self._read(length)
        if mask:
            payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        if opcode == 0x09:
            self._send_control(0x0A, payload)
            return self.receive()
        if opcode == 0x08:
            raise EOFError("Chrome closed the CDP websocket")
        return json.loads(payload.decode("utf-8"))

    def _send_control(self, opcode, payload):
        mask = os.urandom(4)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        self.socket.sendall(bytes((0x80 | opcode, 0x80 | len(payload))) + mask + masked)


class _CDP:
    def __init__(self, websocket):
        self.websocket = websocket
        self.next_id = 1
        self.events = []
        self.requests = []
        self.responses = {}

    def call(self, method, params=None, session=None):
        command_id = self.next_id
        self.next_id += 1
        command = {"id": command_id, "method": method, "params": params or {}}
        if session:
            command["sessionId"] = session
        self.websocket.send(command)
        while True:
            if command_id in self.responses:
                message = self.responses.pop(command_id)
                if "error" in message:
                    raise RuntimeError("CDP %s failed: %r" % (method, message["error"]))
                return message.get("result", {})
            message = self.websocket.receive()
            if message.get("method") == "Network.requestWillBeSent":
                self.requests.append(message["params"]["request"]["url"])
            if message.get("method") == "Fetch.requestPaused":
                self._fulfill_module(message)
                continue
            if message.get("id") == command_id:
                if "error" in message:
                    raise RuntimeError("CDP %s failed: %r" % (method, message["error"]))
                return message.get("result", {})
            if "id" in message:
                self.responses[message["id"]] = message
                continue
            self.events.append(message)

    def _fulfill_module(self, message):
        source = """
export default {
  initialize() {},
  async render(id, source) {
    if (source.includes('safe-diagram')) {
      return {svg: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><style>.node { fill: #2b5f73; }</style><rect class="node" x="1" y="1" width="8" height="8" /></svg>'};
    }
    if (source.includes(%s)) {
      const image = new Image();
      image.src = %s;
      document.body.append(image);
      image.remove();
    }
    return {svg: '<svg xmlns="http://www.w3.org/2000/svg"><image href=%s /></svg>'};
  }
};
""" % (
            json.dumps(ATTACKER_URL),
            json.dumps(ATTACKER_URL),
            json.dumps(ATTACKER_URL),
        )
        self.call(
            "Fetch.fulfillRequest",
            {
                "requestId": message["params"]["requestId"],
                "responseCode": 200,
                "responseHeaders": [
                    {"name": "Content-Type", "value": "application/javascript"},
                    {"name": "Access-Control-Allow-Origin", "value": "*"},
                ],
                "body": base64.b64encode(source.encode("utf-8")).decode("ascii"),
            },
            message.get("sessionId"),
        )


@unittest.skipUnless(next((path for path in CHROME_CANDIDATES if path), None), "Chrome unavailable")
class MermaidBrowserSafety(unittest.TestCase):
    def test_image_node_makes_no_attacker_request_and_keeps_source_readable(self):
        source = 'flowchart LR\nA@{ img: "%s" }' % ATTACKER_URL
        root = ET.fromstring(
            '<canvas ledger="browser-safety" schema="2"><figure id="f2gx" v="1" '
            'payload="mermaid">%s</figure><figure id="f3gx" v="1" '
            'payload="mermaid">flowchart LR\nA --&gt; B</figure><figure id="f4gx" v="1" '
            'payload="mermaid">flowchart LR\nsafe-diagram --&gt; C</figure></canvas>' % source
        )
        _PageHandler.page = render.page("browser-safety", "a" * 40, root, {}).encode()
        server = ThreadingHTTPServer(("127.0.0.1", 0), _PageHandler)
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)

        profile = tempfile.mkdtemp(prefix="canvas-mermaid-chrome-")
        self.addCleanup(shutil.rmtree, profile, True)
        chrome = next(path for path in CHROME_CANDIDATES if path)
        process = subprocess.Popen(
            [
                chrome,
                "--headless=new",
                "--disable-gpu",
                "--no-first-run",
                "--no-default-browser-check",
                "--remote-debugging-port=0",
                "--remote-allow-origins=*",
                "--user-data-dir=%s" % profile,
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.addCleanup(process.wait, 10)
        self.addCleanup(process.terminate)

        port_file = os.path.join(profile, "DevToolsActivePort")
        deadline = time.time() + 10
        while not os.path.exists(port_file) and time.time() < deadline:
            time.sleep(0.05)
        self.assertTrue(os.path.exists(port_file), "Chrome did not expose CDP")
        with open(port_file, encoding="ascii") as handle:
            port, browser_path = handle.read().splitlines()[:2]

        websocket = _WebSocket("ws://127.0.0.1:%s%s" % (port, browser_path))
        self.addCleanup(websocket.close)
        cdp = _CDP(websocket)
        target = cdp.call("Target.createTarget", {"url": "about:blank"})["targetId"]
        session = cdp.call(
            "Target.attachToTarget", {"targetId": target, "flatten": True}
        )["sessionId"]
        cdp.call("Network.enable", session=session)
        cdp.call(
            "Fetch.enable",
            {"patterns": [{"urlPattern": render.MERMAID_MODULE_URL}]},
            session,
        )
        cdp.call("Page.enable", session=session)
        url = "http://127.0.0.1:%s/page.html" % server.server_port
        cdp.call("Page.navigate", {"url": url}, session)

        state = None
        deadline = time.time() + 10
        expression = """(() => {
          const figures = [...document.querySelectorAll('.figure')];
          if (figures.length !== 3 ||
              figures.slice(0, 2).some(figure => !figure.classList.contains('mermaid-failed')) ||
              !figures[2].querySelector('.mermaid-drawing svg')) return null;
          return figures.map(figure => {
            const source = figure.querySelector('[data-mermaid-source]');
            return {text: source.textContent, hidden: source.hidden,
                    drawings: figure.querySelectorAll('.mermaid-drawing').length};
          });
        })()"""
        while state is None and time.time() < deadline:
            result = cdp.call(
                "Runtime.evaluate",
                {"expression": expression, "returnByValue": True},
                session,
            )
            state = result.get("result", {}).get("value")
            if state is None:
                time.sleep(0.05)

        self.assertIsNotNone(state, "unsafe Mermaid result did not reach fallback")
        self.assertEqual(source, state[0]["text"])
        self.assertEqual("flowchart LR\nA --> B", state[1]["text"])
        self.assertFalse(state[0]["hidden"])
        self.assertFalse(state[1]["hidden"])
        self.assertTrue(state[2]["hidden"])
        self.assertEqual([0, 0, 1], [figure["drawings"] for figure in state])
        self.assertNotIn(ATTACKER_URL, cdp.requests)


if __name__ == "__main__":
    unittest.main()
