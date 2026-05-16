"""Danmaku display window using tkinter — Windows only.

Borderless always-on-top overlay with fully transparent background,
click-through, and taskbar icon. Danmaku labels are placed on a
full-screen Canvas container and scrolled leftward each tick.

Multiple danmaku are assigned to separate horizontal rows so they
do not overlap vertically.
"""

import ctypes
import logging
import queue
import tkinter as tk
from typing import Callable, List, Optional

from py_danmaku.utils.font_utils import cjk_font

logger = logging.getLogger(__name__)

# Sentinel colour for tkinter's -transparentcolor attribute.
# Every pixel painted with this exact hex value becomes fully transparent.
_TRANSPARENTCOLOR = "#010101"

# Number of vertical rows into which the screen is divided.
# Each new danmaku picks the first free row.
_NUM_ROWS = 5

# Windows extended-style constants
_GWL_EXSTYLE = -20
_WS_EX_TRANSPARENT = 0x00000020
_WS_EX_LAYERED = 0x00080000
_WS_EX_APPWINDOW = 0x00040000


def _setup_overlay(hwnd: int) -> None:
    """Apply click-through (WS_EX_TRANSPARENT), layered transparency and
    taskbar icon (WS_EX_APPWINDOW)."""
    user32 = ctypes.windll.user32  # pyright: ignore[reportAttributeAccessIssue]
    style = user32.GetWindowLongW(hwnd, _GWL_EXSTYLE)
    style |= _WS_EX_TRANSPARENT | _WS_EX_LAYERED | _WS_EX_APPWINDOW
    user32.SetWindowLongW(hwnd, _GWL_EXSTYLE, style)
    # SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW  — refresh taskbar
    user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0002 | 0x0001 | 0x0040)


# ── Data / display items ────────────────────────────────────────────


class DanmakuItem:
    """A single danmaku message."""

    def __init__(
        self,
        text: str,
        source: str = "unknown",
        speed: float = 2.0,
        color: str = "#FFFFFF",
        font_size: int = 12,
    ):
        self.text = text
        self.source = source
        self.speed = speed
        self.color = color
        self.font_size = font_size


class DanmakuLabel(tk.Label):
    """A single scrolling danmaku label assigned to a fixed row."""

    def __init__(
        self,
        parent: tk.Widget,
        item: DanmakuItem,
        screen_width: int,
        row_h: int,
        row_idx: int,
    ):
        self.screen_width = screen_width
        self._speed = item.speed
        self._row = row_idx
        start_y = row_idx * row_h + row_h // 2

        super().__init__(
            parent,
            text=item.text,
            fg=item.color,
            bg=_TRANSPARENTCOLOR,
            font=cjk_font(item.font_size, bold=True),
        )
        self.place(x=screen_width, y=start_y)

    def tick(self) -> bool:
        """Move leftward.  Return ``False`` when the label has scrolled
        past the left edge and been destroyed."""
        freed = False
        old_x = self.winfo_x()
        new_x = old_x - self._speed
        width = self.winfo_width()
        if new_x + width < self.screen_width and old_x + width >= self.screen_width:
            freed = True
        if new_x < -width:
            self.destroy()
            return freed,True
        self.place(x=new_x)
        return freed,False


# ── Main window ─────────────────────────────────────────────────────


class DanmakuWindow:
    """Borderless always-on-top overlay that renders scrolling danmaku.

    All tkinter operations run on the main thread via ``root.after()``
    callbacks.  The root window is full-screen, transparent, and
    click-through.

    Danmaku are spread across ``_NUM_ROWS`` (18) horizontal rows.  A
    new danmaku always picks the first currently-free row, preventing
    vertical overlap.
    """

    TICK_MS = 20
    QUEUE_POLL_MS = 50

    def __init__(self):
        self.root: Optional[tk.Tk] = None
        self._canvas: Optional[tk.Canvas] = None
        self.running = False

        self._screen_w: int = 1920
        self._screen_h: int = 1080
        self._row_h: int = 28
        self._rows: List[bool] = []
        self._queue: queue.Queue = queue.Queue()
        self._labels: List[DanmakuLabel] = []

    # ── row tracking ────────────────────────────────────────────

    def _pick_row(self) -> int:
        """Return index of the first free row and mark it occupied,
        or 0 when every row is currently in use."""
        for i, free in enumerate(self._rows):
            if free:
                self._rows[i] = False
                return i
        return -1

    def _free_row(self, idx: int) -> None:
        """Mark *idx* as available again."""
        if 0 <= idx < len(self._rows):
            self._rows[idx] = True

    # ── window creation ─────────────────────────────────────────

    def _create_window(self) -> None:
        self.root = tk.Tk()
        self.root.title("Danmaku")
        self.root.attributes("-topmost", True)
        self.root.overrideredirect(True)

        # Transparency colour-key on the root
        try:
            self.root.attributes("-transparentcolor", _TRANSPARENTCOLOR)
            self.root.configure(bg=_TRANSPARENTCOLOR)
        except tk.TclError:
            pass

        self._screen_w = self.root.winfo_screenwidth()
        self._screen_h = self.root.winfo_screenheight()
        self.root.geometry(f"{self._screen_w}x{self._screen_h}+0+0")

        # Canvas fills the root and serves as the container for all labels.
        # Without this intermediate container, tkinter may fail to properly
        # composite child widgets before -transparentcolor is applied.
        self._canvas = tk.Canvas(
            self.root,
            width=self._screen_w,
            height=self._screen_h,
            bg=_TRANSPARENTCOLOR,
            highlightthickness=0,
        )
        self._canvas.pack(fill=tk.BOTH, expand=True)

        # Initialise row tracking
        self._rows = [True] * _NUM_ROWS

        self.root.update_idletasks()
        # _setup_overlay(self.root.winfo_id())
        self.root.deiconify()
        self.root.update()

    # ── queue → label creation ──────────────────────────────────

    def _process_queue(self) -> None:
        if not self.running or self._canvas is None:
            return

        while True:
            try:
                item: DanmakuItem = self._queue.get_nowait()
            except queue.Empty:
                break

            row_idx = self._pick_row()
            if row_idx == -1:
                logger.warning("All rows are currently occupied; dropping danmaku: %s", item.text)
            else:
                label = DanmakuLabel(self._canvas, item, self._screen_w, self._row_h, row_idx)
                self._labels.append(label)
            self._queue.task_done()

        self.root.after(self.QUEUE_POLL_MS, self._process_queue)  # type: ignore[union-attr]

    # ── animation tick ──────────────────────────────────────────

    def _animate(self) -> None:
        if not self.running or self.root is None:
            return

        self.root.update_idletasks()
        for label in self._labels[:]:
            if not label.winfo_exists():
                self._labels.remove(label)
            else:
                freed, removed = label.tick()
                if freed: self._free_row(label._row)
                if removed: self._labels.remove(label)

        self.root.after(self.TICK_MS, self._animate)

    # ── public API ──────────────────────────────────────────────

    def add_danmaku(self, item: DanmakuItem) -> None:
        """Enqueue a danmaku item for display.  Thread-safe."""
        logger.info("received message:%s",item.text)
        self._queue.put(item)

    def start(self, on_ready: Optional[Callable[["tk.Tk"], None]] = None) -> None:
        """Create the window and enter the blocking tkinter mainloop.

        *on_ready* is called (with the root window) after creation but
        before ``mainloop``.
        """
        if self.running:
            return

        self.running = True
        self._create_window()

        if self.root is None:
            return

        self.root.after(self.TICK_MS, self._animate)
        self.root.after(self.QUEUE_POLL_MS, self._process_queue)

        if on_ready:
            on_ready(self.root)

        self.root.mainloop()
        self.running = False

    def stop(self) -> None:
        """Signal the window to close.  Safe to call from any thread."""
        self.running = False
        if self.root is not None:
            try:
                self.root.quit()
            except tk.TclError:
                pass
            try:
                self.root.destroy()
            except tk.TclError:
                pass
            self.root = None
            self._canvas = None

    def is_running(self) -> bool:
        return self.running
