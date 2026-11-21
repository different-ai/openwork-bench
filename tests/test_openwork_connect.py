"""server_info finds the desktop's embedded server over a (fake) DevTools endpoint."""

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

websockets = pytest.importorskip("websockets")

from openwork_bench.harness.openwork_connect import server_info  # noqa: E402


def _start_fake_cdp(value):
    loop = asyncio.new_event_loop()
    ready = threading.Event()
    port_box = {}

    async def handler(ws):
        req = json.loads(await ws.recv())
        assert req["method"] == "Runtime.evaluate" and "openworkServerInfo" in req["params"]["expression"]
        await ws.send(json.dumps({"id": req["id"], "result": {"result": {"type": "object", "value": value}}}))

    async def main():
        server = await websockets.serve(handler, "127.0.0.1", 0)
        port_box["ws"] = server.sockets[0].getsockname()[1]
        ready.set()
        await asyncio.Future()

    threading.Thread(target=lambda: loop.run_until_complete(main()), daemon=True).start()
    ready.wait(5)

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            body = json.dumps(
                [
                    {"type": "service_worker", "webSocketDebuggerUrl": "ws://ignored"},
                    {
                        "type": "page",
                        "url": "app://openwork",
                        "webSocketDebuggerUrl": f"ws://127.0.0.1:{port_box['ws']}/devtools/page/1",
                    },
                ]
            ).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{httpd.server_address[1]}"


def test_server_info_reads_the_embedded_server():
    url = _start_fake_cdp({"baseUrl": "http://127.0.0.1:5186", "token": "owner-token"})
    assert server_info(url) == {"baseUrl": "http://127.0.0.1:5186", "token": "owner-token"}


def test_server_info_fails_clearly_without_a_running_server():
    url = _start_fake_cdp(None)
    with pytest.raises(RuntimeError, match="no OpenWork window"):
        server_info(url)
