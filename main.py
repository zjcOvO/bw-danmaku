import signal
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from typing import Optional

from py_danmaku.utils.logger import setup_logger
from py_danmaku.controller import DanmakuController


class DanmakuApp:
    def __init__(self):
        self.logger = setup_logger()
        self.controller: Optional[DanmakuController] = None
        self._running = False

    def setup_signal_handlers(self):
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        self.logger.info("Signal handlers registered")

    def _signal_handler(self, signum, frame):
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.stop()

    def start(self):
        self.logger.info("Starting py_danmaku application...")
        self.setup_signal_handlers()
        
        self._running = True

        self.controller = DanmakuController()
        self.controller.start() # This will block until the controller is stopped
        
    def stop(self):
        if not self._running:
            return

        self.logger.info("Stopping py_danmaku application...")
        if self.controller:
            self.controller.stop()

        self._running = False
        self.logger.info("py_danmaku application stopped")
        sys.exit(0)


def main():
    app = DanmakuApp()
    app.start()


if __name__ == "__main__":
    main()
