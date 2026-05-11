"""Manual danmaku input popup window."""

import tkinter as tk
import logging
from typing import Callable, Optional, Dict, Any

from py_danmaku.utils.font_utils import cjk_font

logger = logging.getLogger(__name__)


class ManualDanmakuClient:
    """Manual danmaku input source using a tkinter Toplevel popup."""

    def __init__(
        self,
        on_message: Optional[Callable[[Dict[str, Any]], None]] = None,
        username: str = "我",
    ):
        self.on_message = on_message
        self.username = username
        self._running = False
        self._window: Optional[tk.Toplevel] = None
        self._text_entry: Optional[tk.Entry] = None
        self._username_entry: Optional[tk.Entry] = None

    @property
    def is_running(self) -> bool:
        return self._running

    def create_window(self, master: tk.Tk) -> None:
        """Create the manual danmaku input popup as Toplevel of the main window."""
        if self._window is not None:
            self._window.deiconify()
            self._window.lift()
            if self._text_entry:
                self._text_entry.focus_set()
            return

        self._window = tk.Toplevel(master)
        self._window.title("手动弹幕")
        self._window.geometry("420x160")
        self._window.attributes("-topmost", True)
        self._window.resizable(False, False)

        # Username row
        tk.Label(
            self._window, text="用户名:", font=cjk_font(11),
        ).grid(row=0, column=0, padx=(10, 5), pady=(10, 5), sticky="w")
        self._username_entry = tk.Entry(
            self._window, width=32, font=cjk_font(11),
        )
        self._username_entry.grid(row=0, column=1, padx=(0, 10), pady=(10, 5), sticky="ew")
        self._username_entry.insert(0, self.username)

        # Message row
        tk.Label(
            self._window, text="弹幕内容:", font=cjk_font(11),
        ).grid(row=1, column=0, padx=(10, 5), pady=5, sticky="w")
        self._text_entry = tk.Entry(
            self._window, width=32, font=cjk_font(11),
        )
        self._text_entry.grid(row=1, column=1, padx=(0, 10), pady=5, sticky="ew")

        # Button row
        btn_frame = tk.Frame(self._window)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=(5, 10))

        tk.Button(
            btn_frame, text="发送send", command=self._send, width=12,
            font=cjk_font(11),
        ).pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(
            btn_frame, text="隐藏hide", command=self._hide, width=10,
            font=cjk_font(11),
        ).pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(
            btn_frame, text="关闭close", command=self.stop, width=10,
            font=cjk_font(11),
        ).pack(side=tk.LEFT)

        # Bind Enter key in both entries
        self._text_entry.bind("<Return>", lambda e: self._send())
        self._username_entry.bind("<Return>", lambda e: self._send())

        self._window.protocol("WM_DELETE_WINDOW", self._hide)

        # Allow the window column to expand
        self._window.grid_columnconfigure(1, weight=1)

        self._text_entry.focus_set()
        self._running = True
        logger.info("Manual danmaku window created")

    def _send(self) -> None:
        """Send the current text as a danmaku message."""
        if not self._text_entry:
            return
        text = self._text_entry.get().strip()
        if not text:
            return

        username = (
            self._username_entry.get().strip()
            if self._username_entry
            else self.username
        )
        if not username:
            username = self.username

        if self.on_message:
            self.on_message({
                "type": "manual",
                "username": username,
                "text": text,
            })

        self._text_entry.delete(0, tk.END)
        self._text_entry.focus_set()

    def _hide(self) -> None:
        """Hide the window without destroying it."""
        if self._window:
            self._window.withdraw()
        self._running = False
        logger.info("Manual danmaku window hidden")

    def show(self) -> None:
        """Show the window if it was hidden."""
        if self._window:
            self._window.deiconify()
            self._window.lift()
            if self._text_entry:
                self._text_entry.focus_set()
            self._running = True
            logger.info("Manual danmaku window shown")

    def start(self) -> None:
        """Start the manual danmaku client (window created later via create_window)."""
        self._running = True
        logger.info("ManualDanmakuClient started")

    def stop(self) -> None:
        """Stop the client and destroy the window."""
        self._running = False
        if self._window:
            try:
                self._window.destroy()
            except tk.TclError:
                pass
            self._window = None
        logger.info("ManualDanmakuClient stopped")

    def toggle_window(self, master: tk.Tk) -> None:
        """Toggle visibility: create if needed, show/hide otherwise."""
        if self._window is None:
            self.create_window(master)
        elif self._window.winfo_viewable():
            self._hide()
        else:
            self.show()