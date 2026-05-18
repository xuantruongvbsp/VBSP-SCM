"""
Cấu hình logging tập trung cho VBSP-SCM.
Dùng: logger = get_logger(__name__)
"""
import logging
import logging.handlers
from pathlib import Path

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

_LOG_FILE = LOG_DIR / "app.log"
_FMT = "%(asctime)s [%(levelname)s] %(name)s — %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"

_root_configured = False


def _configure_root() -> None:
    global _root_configured
    if _root_configured:
        return

    root = logging.getLogger()
    if root.handlers:
        _root_configured = True
        return

    root.setLevel(logging.DEBUG)

    # File handler — xoay vòng 5 MB × 3 bản sao
    fh = logging.handlers.RotatingFileHandler(
        _LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(_FMT, datefmt=_DATE_FMT))

    # Console handler — chỉ WARNING trở lên để không spam Streamlit terminal
    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)
    ch.setFormatter(logging.Formatter(_FMT, datefmt=_DATE_FMT))

    root.addHandler(fh)
    root.addHandler(ch)
    _root_configured = True


def get_logger(name: str) -> logging.Logger:
    """
    Trả về logger cho module `name`.
    Ghi đồng thời ra logs/app.log (xoay vòng 5 MB×3) và console (WARNING+).
    """
    _configure_root()
    return logging.getLogger(name)
