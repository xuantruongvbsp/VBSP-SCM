"""Tự động phát hiện cấu trúc cột từ file Excel/CSV mẫu để tạo template."""
from __future__ import annotations

import io
import re
from typing import Any

import pandas as pd

from logger import get_logger

logger = get_logger(__name__)

_HEADER_KEYWORDS = [
    "STT", "TT", "ĐƠN VỊ", "TÊN", "SỐ TIỀN", "TỔNG",
    "PGD", "XÃ", "PHƯỜNG", "KH", "KẾ HOẠCH", "CHỈ TIÊU",
]

# Regex La Mã: I, II, ..., XIV, ...
_LA_MA_RE = re.compile(
    r"^M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$",
    re.IGNORECASE,
)


def _la_la_ma(s: str) -> bool:
    s = s.strip()
    return bool(s) and bool(_LA_MA_RE.match(s))


def _dem_keywords(row: list) -> int:
    txt = " ".join(str(c).upper() for c in row if str(c).strip())
    return sum(1 for kw in _HEADER_KEYWORDS if kw in txt)


def _tim_header_row(df_raw: pd.DataFrame) -> int:
    """Tìm hàng header: hàng có nhiều keyword nhất trong 25 hàng đầu."""
    best_idx, best_score = 0, -1
    for i, row in df_raw.head(25).iterrows():
        score = _dem_keywords(row.tolist())
        if score > best_score:
            best_score, best_idx = score, i
    return int(best_idx)


def _tim_cot_stt_ten(header: list) -> tuple[int, int]:
    """Trả về (stt_col, name_col) dạng 1-based."""
    stt_col, name_col = 1, 2
    found_stt = found_name = False
    for i, cell in enumerate(header):
        txt = str(cell).strip().upper()
        if not found_stt and txt in ("STT", "TT", "SỐ TT", "S.TT"):
            stt_col, found_stt = i + 1, True
        elif not found_name and any(kw in txt for kw in ("TÊN", "ĐƠN VỊ", "PGD", "XÃ", "PHƯỜNG")):
            name_col, found_name = i + 1, True
    return stt_col, name_col


def _phat_hien_loai(data_rows: list[list], stt_idx: int) -> str:
    """Detect loại cấu trúc dựa trên cột STT (có La Mã → phân cấp)."""
    roman_count = 0
    for row in data_rows[:60]:
        if len(row) <= stt_idx:
            continue
        val = str(row[stt_idx]).strip()
        if not val:
            continue
        try:
            float(val)
        except (ValueError, TypeError):
            if _la_la_ma(val):
                roman_count += 1
    return "phan_cap_stt" if roman_count > 0 else "phang"


def _loc_cot_du_lieu(header: list, stt_idx: int, name_idx: int) -> list[dict]:
    """Các cột dữ liệu (bỏ STT, Tên, cột trống)."""
    skip = {stt_idx, name_idx}
    cols = []
    for i, cell in enumerate(header):
        if i in skip:
            continue
        ten = str(cell).strip()
        if ten and ten.upper() not in ("", "NAN", "NONE"):
            cols.append({"ten": ten[:40], "col": i + 1})
    return cols


def phat_hien_cau_truc(file_bytes: bytes, filename: str) -> dict[str, Any]:
    """
    Phân tích file Excel/CSV từ bytes, trả về dict cấu hình gợi ý.

    Returns:
        {
            header_row: int (1-based),
            stt_col: int, name_col: int,
            loai_cau_truc: str,
            ds_chuong_trinh: list[dict],
            preview_rows: list[list],   # 8 hàng mẫu sau header
            all_headers: list[str],
        }

    Raises:
        ValueError nếu không đọc được file.
    """
    try:
        buf = io.BytesIO(file_bytes)
        if filename.lower().endswith(".csv"):
            df_raw = pd.read_csv(buf, header=None, dtype=str,
                                 encoding_errors="replace", nrows=80)
        else:
            df_raw = pd.read_excel(buf, header=None, dtype=str, nrows=80)
    except Exception as e:
        logger.error("phat_hien_cau_truc: đọc file — %s", e, exc_info=True)
        raise ValueError(f"Không đọc được file: {e}")

    df_raw = df_raw.fillna("")

    header_idx = _tim_header_row(df_raw)
    header_row = df_raw.iloc[header_idx].tolist()
    data_rows  = df_raw.iloc[header_idx + 1:].values.tolist()

    stt_col, name_col = _tim_cot_stt_ten(header_row)
    loai              = _phat_hien_loai(data_rows, stt_col - 1)
    ds_ct             = _loc_cot_du_lieu(header_row, stt_col - 1, name_col - 1)

    return {
        "header_row":       header_idx + 1,   # 1-based
        "stt_col":          stt_col,
        "name_col":         name_col,
        "loai_cau_truc":    loai,
        "ds_chuong_trinh":  ds_ct[:12],
        "preview_rows":     data_rows[:8],
        "all_headers":      [str(h) for h in header_row],
    }
