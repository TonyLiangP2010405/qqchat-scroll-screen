"""Small Windows platform helpers shared by GUI and automation code."""
import logging
import sys

logger = logging.getLogger(__name__)

_DPI_AWARENESS_SET = False


def enable_dpi_awareness() -> bool:
    """Use physical screen coordinates on Windows when possible."""
    global _DPI_AWARENESS_SET
    if _DPI_AWARENESS_SET:
        return True
    if sys.platform != "win32":
        _DPI_AWARENESS_SET = True
        return True

    try:
        import ctypes

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
        _DPI_AWARENESS_SET = True
        return True
    except Exception as e:
        logger.debug(f"设置DPI感知失败: {e}")
        return False
