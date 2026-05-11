import logging
import tkinter.font as tkfont
from typing import Tuple

logger = logging.getLogger(__name__)

_CJK_FAMILY_CANDIDATES = [
    "Noto Sans CJK SC",
    "WenQuanYi Zen Hei",
    "Noto Sans CJK TC",
    "Source Han Sans SC",
    "Noto Sans CJK JP",
    "Noto Sans CJK HK",
    "Noto Sans CJK KR",
    "AR PL UMing CN",
    "AR PL UKai CN",
    "Microsoft YaHei",
    "SimHei",
    "SimSun",
    "PingFang SC",
    "Heiti SC",
    "Arial Unicode MS",
]

# Lazily populated on first call to cjk_font()
_FONT_FAMILY: str | None = None


def _detect_cjk_family() -> str:
    available = set(tkfont.families())
    for name in _CJK_FAMILY_CANDIDATES:
        if name in available:
            logger.debug("CJK font detected: %s", name)
            return name
    logger.debug("No known CJK font found; falling back to TkDefaultFont")
    return "TkDefaultFont"


def cjk_font(size: int = 11, bold: bool = False) -> Tuple[str, int, str]:
    """Return a font tuple that supports CJK (Chinese / Japanese / Korean).

    Detects the best available CJK font family on first call and caches
    the result.  Falls back to ``TkDefaultFont`` when no known CJK face
    is found.

    Args:
        size: Font size in points.
        bold: Whether to use bold weight.
    """
    global _FONT_FAMILY
    if _FONT_FAMILY is None:
        _FONT_FAMILY = _detect_cjk_family()
    return (_FONT_FAMILY, size, "bold" if bold else "normal")