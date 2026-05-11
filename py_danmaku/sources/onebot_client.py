import json
import logging
import queue
import threading
import time
from typing import Callable, Optional, Dict, Any

import websocket


logger = logging.getLogger(__name__)


class OnebotClient:
    def __init__(
        self,
        ws_url: str,
        group_id: int,
        access_token: Optional[str] = None,
        on_message: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self.ws_url = ws_url
        self.group_id = group_id
        self.access_token = access_token
        self.on_message = on_message

        self._ws: Optional[websocket.WebSocketApp] = None
        self._running = False
        self._reconnect = True
        self._thread: Optional[threading.Thread] = None
        self._heartbeat_interval = 30
        self._last_heartbeat = 0
        self._message_queue: queue.Queue = queue.Queue()
        self._lock = threading.Lock()

    def _build_headers(self) -> Dict[str, str]:
        headers = {}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    def _on_message(self, ws: websocket.WebSocketApp, message: str):
        try:
            data = json.loads(message)
            self._handle_message(data)
        except json.JSONDecodeError:
            logger.warning(f"Received non-JSON message: {message}")

    def _handle_message(self, data: Dict[str, Any]):
        msg_type = data.get("post_type", "")
        if msg_type == "message":
            msg_subtype = data.get("message_type", "")
            if msg_subtype == "group":
                group_id = data.get("group_id")
                if group_id == self.group_id:
                    self._message_queue.put(data)
                    if self.on_message:
                        self.on_message(data)

    def _on_error(self, ws: websocket.WebSocketApp, error: Exception):
        logger.error(f"WebSocket error: {error}")

    def _on_close(self, ws: websocket.WebSocketApp, close_status_code: int, close_msg: str):
        logger.warning(f"WebSocket closed: {close_status_code} - {close_msg}")
        if self._reconnect and self._running:
            logger.info("Attempting to reconnect...")
            self._connect()

    def _on_open(self, ws: websocket.WebSocketApp):
        logger.info("WebSocket connected")
        self._last_heartbeat = time.time()

    def _send_heartbeat(self):
        if self._ws and self._running:
            heartbeat_msg = json.dumps({"action": "get_status", "params": {}})
            try:
                self._ws.send(heartbeat_msg)
                self._last_heartbeat = time.time()
            except Exception as e:
                logger.error(f"Failed to send heartbeat: {e}")

    def _heartbeat_loop(self):
        while self._running:
            time.sleep(self._heartbeat_interval)
            if self._running:
                self._send_heartbeat()

    def _connect(self):
        headers = self._build_headers()
        self._ws = websocket.WebSocketApp(
            self.ws_url,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open,
            header=headers,
        )

        ws_thread = threading.Thread(target=self._ws.run_forever)
        ws_thread.daemon = True
        ws_thread.start()

    def start(self):
        if self._running:
            logger.warning("Client is already running")
            return

        self._running = True
        self._reconnect = True
        self._connect()

        self._thread = threading.Thread(target=self._heartbeat_loop)
        self._thread.daemon = True
        self._thread.start()

        logger.info("OnebotClient started")

    def stop(self):
        self._running = False
        self._reconnect = False
        if self._ws:
            self._ws.close()
        logger.info("OnebotClient stopped")

    def get_message(self, timeout: Optional[float] = 1.0) -> Optional[Dict[str, Any]]:
        try:
            return self._message_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def clear_queue(self):
        with self._lock:
            while not self._message_queue.empty():
                try:
                    self._message_queue.get_nowait()
                except queue.Empty:
                    break

    @staticmethod
    def parse_message(data: Dict[str, Any]) -> Dict[str, Any]:
        result = {
            "message_id": data.get("message_id"),
            "group_id": data.get("group_id"),
            "user_id": data.get("user_id"),
            "nickname": data.get("sender", {}).get("nickname", ""),
            "raw_message": "",
            "text": "",
        }

        message = data.get("message", [])
        if isinstance(message, list):
            text_parts = []
            for msg_seg in message:
                if msg_seg.get("type") == "text":
                    text_parts.append(msg_seg.get("data", {}).get("text", ""))
            result["text"] = "".join(text_parts)
            result["raw_message"] = json.dumps(message)
        elif isinstance(message, str):
            result["text"] = message
            result["raw_message"] = message

        return result
