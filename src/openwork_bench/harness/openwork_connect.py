"""Find a running OpenWork Desktop's embedded server through its Chrome DevTools port.

OpenWork Desktop exposes `window.__OPENWORK_ELECTRON__.invokeDesktop("openworkServerInfo")` to
its renderer; OpenWork's own evals use it the same way (evals/packages/testkit/src/spec/runtime.ts).
The owner token it returns is accepted on client and host routes. It is kept in memory only.
"""

from __future__ import annotations

import json
import urllib.request
from functools import lru_cache
from typing import Any

EXPRESSION = (
    "(async () => { const i = await window.__OPENWORK_ELECTRON__?.invokeDesktop?.('openworkServerInfo');"
    " return i && i.running && i.baseUrl ? { baseUrl: String(i.baseUrl), token: String(i.ownerToken || i.clientToken || '') } : null; })()"
)


async def _evaluate(ws_url: str) -> Any:
    import websockets

    async with websockets.connect(ws_url, max_size=None, open_timeout=10) as ws:
        await ws.send(
            json.dumps(
                {
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {"expression": EXPRESSION, "awaitPromise": True, "returnByValue": True},
                }
            )
        )
        while True:
            msg = json.loads(await ws.recv())
            if msg.get("id") == 1:
                return ((msg.get("result") or {}).get("result") or {}).get("value")


@lru_cache(maxsize=4)
def server_info(cdp_url: str) -> dict[str, str]:
    import anyio

    with urllib.request.urlopen(cdp_url.rstrip("/") + "/json/list", timeout=10) as r:
        targets = json.load(r)
    pages = [
        t
        for t in targets
        if t.get("type") == "page"
        and t.get("webSocketDebuggerUrl")
        and not str(t.get("url", "")).startswith("devtools://")
    ]
    for t in pages:
        value = anyio.run(_evaluate, t["webSocketDebuggerUrl"])
        if isinstance(value, dict) and value.get("baseUrl") and value.get("token"):
            return {"baseUrl": value["baseUrl"], "token": value["token"]}
    raise RuntimeError(
        f"no OpenWork window with a running server found at {cdp_url} ({len(pages)} pages checked)"
    )
