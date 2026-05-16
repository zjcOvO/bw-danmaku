"""
Integration controller for the danmaku application.

Coordinates OnebotClient, BilibiliClient, and DanmakuWindow to provide
a unified interface for receiving and displaying messages from multiple
sources.
"""

import logging
import queue
import threading
import time
import tkinter as tk
from typing import Any, Callable, Dict, Optional

from py_danmaku.config import Config
from py_danmaku.sources.bilibili_client import BilibiliClient
from py_danmaku.sources.manual_client import ManualDanmakuClient
from py_danmaku.sources.onebot_client import OnebotClient
from py_danmaku.display.danmaku_window import DanmakuWindow, DanmakuItem
from py_danmaku.utils.logger import setup_logger


logger = setup_logger(__name__)


class DanmakuController:
    """
    Main integration controller for the danmaku application.

    Coordinates message receiving from Onebot and Bilibili sources,
    routes messages to the display window, and provides callback
    functionality for external message handling.
    """

    # Message source colors for visual distinction
    SOURCE_COLORS = {
        "onebot": "#15b5e9",  # Blue for QQ/Onebot messages
        "bilibili": "#FF69B4",  # Pink for Bilibili messages
        "manual": "#FFEFD5",  # BlanchedAlmond for manual danmaku
        "unknown": "#FFFFFF",  # White for unknown sources
    }

    def __init__(self, config: Optional[Config] = None):
        """
        Initialize the controller with configuration.

        Args:
            config: Configuration object. If None, loads from default location.
        """
        self._config = config or Config()

        # Client instances
        self._onebot_client: Optional[OnebotClient] = None
        self._bilibili_client: Optional[BilibiliClient] = None
        self._manual_client: Optional[ManualDanmakuClient] = None
        self._danmaku_window: Optional[DanmakuWindow] = None

        # Internal state
        self._running = False
        self._message_loop_thread: Optional[threading.Thread] = None
        self._message_callbacks: list = []

        # Thread-safe message queue
        self._message_queue: queue.Queue = queue.Queue()

        # Source colors
        self._onebot_color = self.SOURCE_COLORS.get("onebot")
        self._bilibili_color = self.SOURCE_COLORS.get("bilibili")

        # Initialize components
        self._initialize_clients()
        self._initialize_window()

        logger.info("DanmakuController initialized")

    def _initialize_clients(self):
        """Initialize Onebot and Bilibili clients based on configuration."""
        # Create Onebot client if enabled in config
        self._onebot_client = self._create_onebot_client()
        if self._onebot_client:
            logger.info("Onebot client created")

        # Create Bilibili client if enabled in config
        self._bilibili_client = self._create_bilibili_client()
        if self._bilibili_client:
            logger.info("Bilibili client created")

        # Create manual danmaku client (always available)
        self._manual_client = self._create_manual_client()
        logger.info("Manual danmaku client created")

    def _create_onebot_client(self) -> Optional[OnebotClient]:
        """
        Create Onebot client from configuration.

        Returns:
            OnebotClient instance or None if disabled/not configured.
        """
        onebot_config = self._config.onebot
        if not onebot_config:
            logger.warning("No Onebot configuration found")
            return None

        ws_url = onebot_config.get("ws_url")
        group_id = onebot_config.get("group_id")
        access_token = onebot_config.get("access_token")

        # Check if Onebot is disabled (empty or disabled config)
        if not ws_url or not group_id:
            logger.info("Onebot client is disabled")
            return None

        return OnebotClient(
            ws_url=ws_url,
            group_id=group_id,
            access_token=access_token,
            on_message=self._on_source_message,
        )

    def _create_bilibili_client(self) -> Optional[BilibiliClient]:
        """
        Create Bilibili client from configuration.

        Returns:
            BilibiliClient instance or None if disabled/not configured.
        """
        bilibili_config = self._config.bilibili
        if not bilibili_config:
            logger.warning("No Bilibili configuration found")
            return None

        room_id = bilibili_config.get("room_id")
        cookie = bilibili_config.get("cookie")

        # Check if Bilibili is disabled (room_id is 0 or not set)
        if not room_id or room_id == 0:
            logger.info("Bilibili client is disabled (no room_id)")
            return None

        return BilibiliClient(
            room_id=room_id,
            cookie=cookie,
            on_message=self._on_source_message,
        )

    def _create_manual_client(self) -> ManualDanmakuClient:
        """
        Create manual danmaku client (always available).

        Returns:
            ManualDanmakuClient instance.
        """
        manual_config = self._config.manual
        username = manual_config.get("username", "我") if manual_config else "我"
        return ManualDanmakuClient(
            on_message=self._on_source_message,
            username=username,
        )

    def _create_danmaku_window(self) -> DanmakuWindow:
        return DanmakuWindow()

    def _initialize_window(self):
        """Initialize the danmaku display window."""
        self._danmaku_window = self._create_danmaku_window()
        logger.info("Danmaku window created")

    def _on_window_ready(self, root: "tk.Tk") -> None:
        """Callback invoked when the danmaku window is ready.

        Creates the manual danmaku popup window.

        Args:
            root: The tkinter root window (tk.Tk instance).
        """
        if self._manual_client and self._danmaku_window:
            self._manual_client.create_window(root)
            logger.info("Manual danmaku popup created")

    def _on_source_message(self, message: Dict[str, Any]) -> None:
        """
        Callback for handling messages from any source.

        Args:
            message: Message dictionary from Onebot or Bilibili.
        """
        try:
            # Determine message source and format accordingly
            if "group_id" in message:
                # Onebot message
                source = "onebot"
                parsed = OnebotClient.parse_message(message)
                text = parsed.get("text", "")
                username = parsed.get("nickname", "Unknown")
                display_text = text     # f"[{username}]: {text}"
            elif message.get("type") == "bilibili":
                source = "bilibili"
                username = message.get("uname", "Unknown")
                text = message.get("message", "")
                display_text = text     # f"[{username}]: {text}"
            elif message.get("type") == "manual":
                source = "manual"
                username = message.get("username", "我")
                text = message.get("text", "")
                display_text = text     # f"[{username}]: {text}"
            else:
                # Unknown source
                source = "unknown"
                username = "Unknown"
                display_text = str(message)

            # Normalise whitespace: newlines → spaces, collapse runs
            display_text = ' '.join(display_text.split())
            # Discard empty or overlong messages
            if not display_text or len(display_text) > 50 or display_text[0] == '#':
                logger.info("Discarded message (%d chars): %s", len(display_text), display_text[:30])
                return

            # Get color for this source
            color = self.SOURCE_COLORS.get(source, self.SOURCE_COLORS["unknown"])
            
            # 添加一些彩蛋规则
            logger.info("message send by %s:%s",username,display_text)
            if username == "千嶂夹城": #（本项目作者）
                color = "#FFD700"  # 金色传说！（夹带私货）
            elif username == "黄瓜" or username == "群主":
                color = "#0eb83b"  # 绿色
            elif username == "咖啡":
                color = "#cc8e34"  # 咖啡色

            # Create danmaku item
            display = self._config.display or {}
            danmaku_item = DanmakuItem(
                text=display_text,
                source=source,
                color=color,
                speed=display.get("speed", 2.0),
                font_size=display.get("font_size", 36),
            )

            # Add to window queue
            if self._danmaku_window:
                self._danmaku_window.add_danmaku(danmaku_item)

            # Put in internal queue for message loop processing
            self._message_queue.put({
                "source": source,
                "message": message,
                "text": display_text,
            })

            # Call registered callbacks
            for callback in self._message_callbacks:
                try:
                    callback(source, message)
                except Exception as e:
                    logger.error(f"Error in message callback: {e}")

        except Exception as e:
            logger.error(f"Error processing source message: {e}")

    def _message_loop(self) -> None:
        """Background thread for processing messages from all sources."""
        while self._running:
            try:
                # Get message from queue with timeout
                msg = self._message_queue.get(timeout=0.5)

                # Process message (already handled in _on_source_message)
                self._message_queue.task_done()

            except queue.Empty:
                # No message available, continue loop
                pass
            except Exception as e:
                logger.error(f"Error in message loop: {e}")

    def set_message_callback(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """
        Register a callback function for incoming messages.

        Args:
            callback: Function that takes (source, message) as arguments.
        """
        if callback not in self._message_callbacks:
            self._message_callbacks.append(callback)
            logger.info(f"Message callback registered: {callback.__name__}")

    def start(self) -> None:
        """
        Start all components of the danmaku system.

        Starts the Onebot client, Bilibili client, and danmaku window.
        Clients and message loop run in background threads; the danmaku
        window blocks via tkinter mainloop on the calling thread.
        """
        if self._running:
            logger.warning("Controller is already running")
            return

        self._running = True

        self._message_loop_thread = threading.Thread(target=self._message_loop, daemon=True)
        self._message_loop_thread.start()
        logger.info("Message loop started")

        if self._onebot_client:
            self._onebot_client.start()
            logger.info("Onebot client started")

        if self._bilibili_client:
            self._bilibili_client.start()
            logger.info("Bilibili client started")

        if self._manual_client:
            self._manual_client.start()
            logger.info("Manual danmaku client started")

        if self._danmaku_window:
            logger.info("Starting danmaku window (blocking)...")
            self._danmaku_window.add_danmaku(DanmakuItem(
                text="bw_danmaku 项目已启动 — 等待弹幕中...",
                source="system",
                color="#FFD700"
            ))
            self._danmaku_window.start(on_ready=self._on_window_ready)
            logger.info("Danmaku window closed")

        logger.info("DanmakuController started successfully")

    def stop(self) -> None:
        """
        Stop all components of the danmaku system.

        Stops the Bilibili client, Onebot client, and danmaku window.
        """
        if not self._running:
            logger.warning("Controller is not running")
            return

        self._running = False

        # Stop Bilibili client first (has async cleanup)
        if self._bilibili_client:
            self._bilibili_client.stop()
            logger.info("Bilibili client stopped")

        # Stop Onebot client
        if self._onebot_client:
            self._onebot_client.stop()
            logger.info("Onebot client stopped")

        # Stop manual danmaku client
        if self._manual_client:
            self._manual_client.stop()
            logger.info("Manual danmaku client stopped")

        # Stop danmaku window
        if self._danmaku_window:
            self._danmaku_window.stop()
            logger.info("Danmaku window stopped")

        # Wait for message loop to finish
        if self._message_loop_thread:
            self._message_loop_thread.join(timeout=2)
            logger.info("Message loop stopped")

        logger.info("DanmakuController stopped successfully")

    @property
    def is_running(self) -> bool:
        """
        Check if the controller is currently running.

        Returns:
            True if running, False otherwise.
        """
        return self._running

    @property
    def onebot_client(self) -> Optional[OnebotClient]:
        """Get the Onebot client instance."""
        return self._onebot_client

    @property
    def bilibili_client(self) -> Optional[BilibiliClient]:
        """Get the Bilibili client instance."""
        return self._bilibili_client

    @property
    def manual_client(self) -> Optional[ManualDanmakuClient]:
        """Get the manual danmaku client instance."""
        return self._manual_client

    @property
    def danmaku_window(self) -> Optional[DanmakuWindow]:
        """Get the danmaku window instance."""
        return self._danmaku_window
