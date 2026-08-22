"""Dosyaya ve arayüze log yazan basit logger."""
import logging
import sys
from datetime import datetime
from pathlib import Path

if getattr(sys, "frozen", False):
    LOG_FILE = Path(sys.executable).resolve().parent / "uyap_login.log"
else:
    LOG_FILE = Path(__file__).resolve().parent.parent / "uyap_login.log"


class GuiHandler(logging.Handler):
    """Log kayıtlarını arayüzdeki bir callback'e iletir."""

    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def emit(self, record):
        try:
            self.callback(self.format(record))
        except Exception:
            pass


def get_logger(gui_callback=None) -> logging.Logger:
    logger = logging.getLogger("uyap_login")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    stream = logging.StreamHandler()
    stream.setFormatter(fmt)
    logger.addHandler(stream)

    if gui_callback is not None:
        gui = GuiHandler(gui_callback)
        gui.setFormatter(fmt)
        logger.addHandler(gui)

    return logger
