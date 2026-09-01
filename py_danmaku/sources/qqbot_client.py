"""QQ 官方机器人（API v2）群消息客户端。

通过官方 WebSocket 网关接收 QQ 群的 @机器人 / 全量群消息事件
（GROUP_AT_MESSAGE_CREATE / GROUP_MESSAGE_CREATE），解析后交给
on_message 回调，从而把 QQ 群消息投递到弹幕显示。

协议要点（QQ 开放平台 API v2）：
  * 先调用 https://bots.qq.com/app/getAppAccessToken 用 AppID/AppSecret
    换取 access_token（约 2 小时有效）。
  * 连接 WebSocket 网关 wss://api.sgroup.qq.com/websocket。
  * 收到 HELLO(op=10) 后发送 IDENTIFY(op=2)（携带 token 与 intents）。
  * 每隔 heartbeat_interval 发送 HEARTBEAT(op=1)。
  * 群消息事件属于 GROUP_AND_C2C_EVENT(intent = 1 << 25) 订阅。
"""

import json
import logging
import queue
import re
import threading
import time
import urllib.request
from typing import Any, Callable, Dict, Optional

import websocket

logger = logging.getLogger(__name__)

# 网关与接口地址
DEFAULT_GATEWAY = "wss://api.sgroup.qq.com/websocket"
TOKEN_URL = "https://bots.qq.com/app/getAppAccessToken"
API_BASE = "https://api.sgroup.qq.com"

# 群 / C2C 事件订阅 intent
GROUP_AND_C2C_INTENT = 1 << 25

# WebSocket opcode
OP_DISPATCH = 0
OP_HEARTBEAT = 1
OP_IDENTIFY = 2
OP_RESUME = 6
OP_RECONNECT = 7
OP_INVALID_SESSION = 9
OP_HELLO = 10
OP_HEARTBEAT_ACK = 11

# 我们关心的群消息事件类型
GROUP_MESSAGE_EVENTS = ("GROUP_AT_MESSAGE_CREATE", "GROUP_MESSAGE_CREATE")


class QQBotClient:
    """接收 QQ 官方机器人群消息的客户端。

    与 OnebotClient 保持一致的接口（start/stop/on_message/消息队列），
    便于在 DanmakuController 中统一接入。
    """

    def __init__(
        self,
        appid: str,
        appsecret: str,
        group_openid: Optional[str] = None,
        on_message: Optional[Callable[[Dict[str, Any]], None]] = None,
        fetch_nickname: bool = True,
        gateway: str = DEFAULT_GATEWAY,
    ):
        self.appid = appid
        self.appsecret = appsecret
        # 可选：只接收指定群的 openid（QQ 官方 API 用 group_openid，而不是群号）
        self.group_openid = group_openid
        self.on_message = on_message
        self.fetch_nickname = fetch_nickname
        self.gateway = gateway
        self._intents = GROUP_AND_C2C_INTENT

        # WebSocket 状态
        self._ws: Optional[websocket.WebSocketApp] = None
        self._running = False
        self._reconnect = True
        self._identified = False
        self._heartbeat_interval = 0.0
        self._seq = 0
        self._session_id: Optional[str] = None

        # access_token 缓存
        self._access_token: Optional[str] = None
        self._token_expiry = 0.0

        # 线程与队列
        self._thread: Optional[threading.Thread] = None
        self._message_queue: queue.Queue = queue.Queue()

        # 群成员昵称缓存（group_openid:member_openid -> nickname）
        self._nickname_cache: Dict[str, str] = {}

    # ── access_token ─────────────────────────────────────────────────

    def _post_json(self, url: str, payload: Dict[str, Any], timeout: float = 10.0) -> Dict[str, Any]:
        """向 QQ 开放平台发送 JSON POST 请求。"""
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _fetch_access_token(self) -> str:
        """调用获取访问凭证接口换取 access_token。"""
        resp = self._post_json(TOKEN_URL, {"appId": self.appid, "clientSecret": self.appsecret})
        token = resp.get("access_token")
        if not token:
            raise RuntimeError(f"QQ bot failed to get access_token: {resp}")
        expires_in = int(resp.get("expires_in", 7200))
        # 提前 60s 过期，避免临界点失效
        self._access_token = token
        self._token_expiry = time.time() + max(expires_in - 60, 60)
        logger.info("QQ bot access_token refreshed (expires in %ss)", expires_in)
        return token

    def _get_access_token(self) -> str:
        """获取有效 access_token（带缓存）。"""
        if self._access_token and time.time() < self._token_expiry:
            return self._access_token
        return self._fetch_access_token()

    # ── WebSocket ────────────────────────────────────────────────────

    def _on_open(self, ws: websocket.WebSocketApp):
        logger.info("QQ websocket connected")

    def _on_error(self, ws: websocket.WebSocketApp, error: Exception):
        logger.error("QQ websocket error: %s", error)

    def _on_close(self, ws: websocket.WebSocketApp, close_status_code: int, close_msg: str):
        logger.warning("QQ websocket closed: %s - %s", close_status_code, close_msg)
        self._identified = False
        if self._reconnect and self._running:
            logger.info("QQ websocket reconnecting in 3s...")
            threading.Timer(3.0, self._safe_reconnect).start()

    def _safe_reconnect(self):
        """在后台线程安全地重连（失败则带退避重试）。"""
        if not self._running:
            return
        try:
            self._connect()
        except Exception as e:
            logger.error("QQ reconnect failed: %s", e)
            if self._reconnect and self._running:
                threading.Timer(5.0, self._safe_reconnect).start()

    def _on_message(self, ws: websocket.WebSocketApp, message: str):
        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            logger.warning("QQ websocket received non-JSON message: %s", message[:200])
            return
        self._handle_payload(payload)

    def _connect(self):
        try:
            token = self._get_access_token()
        except Exception as e:
            logger.error("Failed to get QQ access token: %s", e)
            if self._reconnect and self._running:
                threading.Timer(5.0, self._safe_reconnect).start()
            return
        self._ws = websocket.WebSocketApp(
            self.gateway,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open,
        )
        ws_thread = threading.Thread(target=self._ws.run_forever)
        ws_thread.daemon = True
        ws_thread.start()
        logger.info("QQ websocket connecting (token used: %s...)", token[:8] if token else "")

    def _send_identify(self):
        if not self._ws:
            return
        token = self._get_access_token()
        payload = {
            "op": OP_IDENTIFY,
            "d": {
                "token": f"QQBot {token}",
                "intents": self._intents,
                "shard": [0, 1],
                "properties": {
                    "$os": "windows",
                    "$browser": "bw-danmaku",
                    "$device": "bw-danmaku",
                },
            },
        }
        self._ws.send(json.dumps(payload))
        self._identified = True
        logger.info("QQ bot IDENTIFY sent")

    def _send_resume(self):
        if not self._ws:
            return
        token = self._get_access_token()
        payload = {
            "op": OP_RESUME,
            "d": {
                "token": f"QQBot {token}",
                "session_id": self._session_id,
                "seq": self._seq,
            },
        }
        self._ws.send(json.dumps(payload))
        self._identified = True
        logger.info("QQ bot RESUME sent (session=%s seq=%s)", self._session_id, self._seq)

    def _handle_payload(self, payload: Dict[str, Any]):
        op = payload.get("op")
        try:
            if op == OP_HELLO:
                interval = (payload.get("d") or {}).get("heartbeat_interval", 41250)
                self._heartbeat_interval = max(float(interval) / 1000.0, 1.0)
                if self._session_id and self._seq:
                    self._send_resume()
                else:
                    self._send_identify()
            elif op == OP_DISPATCH:
                self._handle_dispatch(payload)
            elif op == OP_HEARTBEAT_ACK:
                logger.debug("QQ heartbeat ack received")
            elif op == OP_RECONNECT:
                logger.warning("QQ server requested RECONNECT")
                if self._ws:
                    self._ws.close()
            elif op == OP_INVALID_SESSION:
                logger.warning("QQ INVALID_SESSION, re-identifying")
                self._session_id = None
                self._seq = 0
                self._send_identify()
            else:
                logger.debug("QQ unknown opcode: %s", op)
        except Exception as e:
            logger.error("Error handling QQ websocket payload: %s", e)

    def _handle_dispatch(self, payload: Dict[str, Any]):
        t = payload.get("t")
        d = payload.get("d") or {}
        seq = payload.get("s")
        if seq:
            self._seq = seq

        if t == "READY":
            self._session_id = d.get("session_id")
            logger.info("QQ bot READY (session=%s)", self._session_id)
            return

        if t in GROUP_MESSAGE_EVENTS:
            group_openid = d.get("group_openid")
            if self.group_openid and group_openid != self.group_openid:
                logger.debug("Ignoring message from unconfigured group %s", group_openid)
                return

            message = self.parse_message(payload)
            if self.fetch_nickname and message.get("member_openid"):
                message["nickname"] = self._resolve_nickname(
                    message["group_openid"], message["member_openid"]
                )

            self._message_queue.put(message)
            if self.on_message:
                try:
                    self.on_message(message)
                except Exception as e:
                    logger.error("Error in QQ on_message callback: %s", e)
            logger.info("QQ group message from %s: %s", message["nickname"], message["text"])

    # ── 群成员昵称（best-effort，带缓存）────────────────────────────

    def _fetch_member_nickname(self, group_openid: str, member_openid: str) -> str:
        """调用成员信息接口获取群成员昵称，失败时回退为 member_openid。"""
        if not group_openid or not member_openid:
            return member_openid
        try:
            token = self._get_access_token()
            url = f"{API_BASE}/v2/groups/{group_openid}/members/{member_openid}"
            req = urllib.request.Request(
                url, headers={"Authorization": f"QQBot {token}"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data.get("nick") or member_openid
        except Exception as e:
            logger.warning("Failed to fetch nickname for %s: %s", member_openid, e)
            return member_openid

    def _resolve_nickname(self, group_openid: str, member_openid: str) -> str:
        key = f"{group_openid}:{member_openid}"
        if key in self._nickname_cache:
            return self._nickname_cache[key]
        nickname = self._fetch_member_nickname(group_openid, member_openid)
        self._nickname_cache[key] = nickname
        return nickname

    # ── 生命周期 ─────────────────────────────────────────────────────

    def start(self):
        if self._running:
            logger.warning("QQBotClient is already running")
            return

        self._running = True
        self._reconnect = True
        self._connect()

        self._thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._thread.start()
        logger.info("QQBotClient started")

    def stop(self):
        self._running = False
        self._reconnect = False
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
        logger.info("QQBotClient stopped")

    def _heartbeat_loop(self):
        while self._running:
            if self._heartbeat_interval <= 0:
                time.sleep(1.0)
                continue
            time.sleep(self._heartbeat_interval)
            if self._running and self._ws and self._identified:
                try:
                    self._ws.send(json.dumps({"op": OP_HEARTBEAT, "d": self._seq}))
                except Exception as e:
                    logger.error("Failed to send QQ heartbeat: %s", e)

    # ── 消息队列（与其他数据源接口保持一致）───────────────────────

    def get_message(self, timeout: Optional[float] = 1.0) -> Optional[Dict[str, Any]]:
        try:
            return self._message_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def clear_queue(self):
        while not self._message_queue.empty():
            try:
                self._message_queue.get_nowait()
            except queue.Empty:
                break

    # ── 消息解析 ─────────────────────────────────────────────────────

    @staticmethod
    def parse_message(data: Dict[str, Any]) -> Dict[str, Any]:
        """把群消息事件解析为统一的弹幕消息字典。

        Args:
            data: WebSocket DISPATCH 的完整 payload（含 t / d），
                  或直接传事件体 d。

        Returns:
            {"type": "qqbot", "text": ..., "nickname": ..., ...}
        """
        d = data.get("d", {}) if isinstance(data.get("d"), dict) else data
        event_type = data.get("t", "")

        group_openid = d.get("group_openid", "")
        author = d.get("author", {}) or {}
        member_openid = author.get("member_openid") or author.get("user_openid") or ""

        content = str(d.get("content", "") or "")
        # 去掉 @ 提及标记与零宽字符
        content = re.sub(r"<@!?[^>]*>", "", content)
        content = content.replace("\u200b", "")

        return {
            "type": "qqbot",
            "event_type": event_type,
            "message_id": d.get("msg_id") or d.get("id") or d.get("event_id"),
            "group_openid": group_openid,
            "member_openid": member_openid,
            "nickname": member_openid,
            "timestamp": d.get("timestamp"),
            "msg_type": d.get("msg_type"),
            "text": content.strip(),
            "raw_message": json.dumps(d, ensure_ascii=False),
        }
