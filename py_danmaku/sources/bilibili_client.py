"""
Bilibili live danmaku client implementation.

Provides async connection to Bilibili live streaming danmaku server
using the bilibili-api library (v2+).
"""

import asyncio
import logging
import queue
import threading
from typing import Callable, Optional, Dict, Any

try:
    from bilibili_api.live import LiveDanmaku  # type: ignore[reportMissingImports]
    BILIBILI_API_AVAILABLE = True
except ImportError:
    BILIBILI_API_AVAILABLE = False
    LiveDanmaku = None  # type: ignore[assignment]

from py_danmaku.utils.logger import setup_logger


class BilibiliClient:
    """
    Bilibili live danmaku client.

    Connects to a Bilibili live room and receives real-time danmaku messages
    through a thread-safe message queue.
    """

    def __init__(
        self,
        room_id: int,
        cookie: Optional[str] = None,
        on_message: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        self.room_id = room_id
        self.cookie = cookie
        self.on_message = on_message
        self._logger = setup_logger("bilibili_client")

        self._message_queue: queue.Queue = queue.Queue()

        self._is_running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._danmaku: Optional[LiveDanmaku] = None  # type: ignore[valid-type]

        self._logger.info("BilibiliClient initialized for room %s", room_id)

    @property
    def is_running(self) -> bool:
        return self._is_running

    def start(self) -> None:
        if self._is_running:
            self._logger.warning("Client is already running")
            return

        if not BILIBILI_API_AVAILABLE:
            self._logger.warning("bilibili-api not installed; danmaku client disabled")
            return

        self._is_running = True
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._logger.info("Started danmaku client for room %s", self.room_id)

    def stop(self) -> None:
        if not self._is_running:
            return

        self._is_running = False

        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

        if self._thread:
            self._thread.join(timeout=5)

        self._logger.info("Stopped danmaku client for room %s", self.room_id)

    def get_message(self, timeout: float = 0.1) -> Optional[Dict[str, Any]]:
        try:
            return self._message_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def clear_queue(self) -> None:
        while not self._message_queue.empty():
            try:
                self._message_queue.get_nowait()
            except queue.Empty:
                break
        self._logger.debug("Message queue cleared")

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connect())
        except Exception as e:
            self._logger.error("Error in danmaku connection: %s", e)
        finally:
            self._is_running = False

    async def _connect(self) -> None:
        try:
            import bilibili_api.live as _live

            _get_room_play_info = _live.get_room_play_info
            _live.get_room_play_info = lambda room_display_id, **kw: {"room_id": room_display_id}

            danmaku = LiveDanmaku(self.room_id, verify=None, should_reconnect=False)
            self._danmaku = danmaku
            danmaku.add_event_handler("DANMU_MSG", self._on_danmaku)

            if self.cookie:
                danmaku.verify = self._build_verify()

            connect_coro = danmaku.connect(return_coroutine=True)
            await asyncio.wait_for(connect_coro, timeout=30)

            _live.get_room_play_info = _get_room_play_info

        except asyncio.TimeoutError:
            self._logger.error("Connection to danmaku server timed out (30s)")
            self._is_running = False
        except Exception as e:
            self._logger.error("Failed to connect to danmaku server: %s", e)
            self._is_running = False

    def _build_verify(self):
        from bilibili_api.utils import Verify
        if not self.cookie:
            return None
        try:
            if isinstance(self.cookie, dict):
                cookie_dict = self.cookie
            elif isinstance(self.cookie, str):
                cookie_dict = {}
                for item in self.cookie.split(";"):
                    if "=" in item:
                        key, value = item.strip().split("=", 1)
                        cookie_dict[key] = value
            else:
                return None
            return Verify(
                sessdata=cookie_dict.get("SESSDATA", ""),
                csrf=cookie_dict.get("bili_jct", ""),
                buvid3=cookie_dict.get("BUVID3", ""),
            )
        except Exception:
            return None

    def _on_danmaku(self, event: Dict[str, Any]) -> None:
        try:
            data = event.get("data", {})

            if isinstance(data, dict) and "info" in data:
                danmaku_info = data["info"]
                if isinstance(danmaku_info, list) and len(danmaku_info) >= 3:
                    msg_params = danmaku_info[0]
                    msg_text = danmaku_info[1] if len(danmaku_info) > 1 else ""
                    user_info = danmaku_info[2] if len(danmaku_info) > 2 else []

                    if isinstance(msg_params, list) and len(msg_params) >= 9:
                        mode = msg_params[1]
                        fontsize = msg_params[2]
                        color = msg_params[3]
                        ctime = msg_params[4]
                        msg_type = msg_params[8]
                    else:
                        mode = 0
                        fontsize = 0
                        color = 0
                        ctime = 0
                        msg_type = 0

                    if isinstance(user_info, list) and len(user_info) >= 2:
                        uid = user_info[0]
                        uname = user_info[1]
                    else:
                        uid = 0
                        uname = ""

                    message = {
                        "type": "bilibili",
                        "room_id": self.room_id,
                        "msg_type": msg_type,
                        "mode": mode,
                        "fontsize": fontsize,
                        "color": color,
                        "mid": uid,
                        "uname": str(uname),
                        "message": str(msg_text),
                        "ctime": ctime,
                    }
                else:
                    message = {
                        "type": "bilibili",
                        "room_id": self.room_id,
                        "msg_type": 0,
                        "mode": 0,
                        "fontsize": 0,
                        "color": 0,
                        "mid": 0,
                        "uname": "",
                        "message": str(data),
                        "ctime": 0,
                    }
            else:
                message = {
                    "type": "bilibili",
                    "room_id": self.room_id,
                    "uname": "",
                    "message": str(data),
                }

            self._message_queue.put(message)

            if self.on_message:
                self.on_message(message)

            self._logger.debug("Received danmaku: %s", message.get("message", ""))

        except Exception as e:
            self._logger.error("Error processing danmaku: %s", e)

    def __del__(self):
        if self._is_running:
            self.stop()