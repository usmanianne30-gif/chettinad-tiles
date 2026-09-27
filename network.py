"""
network.py – Thread-safe WebSocket client wrapper for Chettinad Tiles.
Runs the WebSocket event-loop in a background thread so pygame doesn't block.
"""
from __future__ import annotations
import asyncio
import json
import queue
import threading
import logging
from typing import Optional

import websockets

log = logging.getLogger("network")

# ── Public server URL (change to your Render/Railway deployment) ──────────
# If running locally, use "ws://localhost:8765"
SERVER_URL = "wss://chettinad-tiles.onrender.com"
LOCAL_URL  = "ws://localhost:8765"


class NetworkClient:
    """
    Thread-safe interface between the pygame main thread and the asyncio WS loop.

    Usage:
        net = NetworkClient()
        net.connect(url)            # non-blocking
        net.send({"type": "ping"})  # non-blocking
        msg = net.recv()            # returns dict or None (non-blocking poll)
        net.disconnect()
    """

    def __init__(self):
        self._send_q:  queue.Queue[Optional[dict]] = queue.Queue()
        self._recv_q:  queue.Queue[dict]           = queue.Queue()
        self._thread:  Optional[threading.Thread]  = None
        self._loop:    Optional[asyncio.AbstractEventLoop] = None
        self.connected = False
        self.error: Optional[str] = None
        self._url: str = SERVER_URL

    # ── public API (called from main thread) ─────────────────────────────
    def connect(self, url: str = SERVER_URL):
        self._url = url
        if self._thread and self._thread.is_alive():
            return
        self.connected = False
        self.error     = None
        self._thread   = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def disconnect(self):
        self._send_q.put(None)      # sentinel → close connection

    def send(self, data: dict):
        self._send_q.put(data)

    def recv(self) -> Optional[dict]:
        """Non-blocking poll; returns one message or None."""
        try:
            return self._recv_q.get_nowait()
        except queue.Empty:
            return None

    # ── background thread ─────────────────────────────────────────────────
    def _run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._ws_loop())
        except Exception as e:
            self.error = str(e)
            log.error(f"Network error: {e}")
        finally:
            self._loop.close()

    async def _ws_loop(self):
        try:
            async with websockets.connect(self._url, ping_interval=20, ping_timeout=20) as ws:
                self.connected = True
                log.info(f"Connected to {self._url}")
                self._recv_q.put({"type": "_connected"})

                send_task = asyncio.create_task(self._sender(ws))
                recv_task = asyncio.create_task(self._receiver(ws))
                done, pending = await asyncio.wait(
                    [send_task, recv_task],
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for t in pending:
                    t.cancel()
        except Exception as e:
            self.error = str(e)
            self._recv_q.put({"type": "_error", "msg": str(e)})
        finally:
            self.connected = False

    async def _sender(self, ws):
        loop = asyncio.get_event_loop()
        while True:
            # Poll the queue without blocking the event loop
            try:
                data = self._send_q.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.02)
                continue
            if data is None:    # disconnect sentinel
                await ws.close()
                return
            try:
                await ws.send(json.dumps(data))
            except Exception as e:
                log.warning(f"Send error: {e}")
                return

    async def _receiver(self, ws):
        async for raw in ws:
            try:
                msg = json.loads(raw)
                self._recv_q.put(msg)
            except Exception:
                pass
