"""Đọc và tổng hợp dữ liệu Chấm điểm Tổ TK&VV (CDTOTKVV)."""
import os
import re
import unicodedata
from pathlib import Path

import pandas as pd
import streamlit as st

from config import BASE_DIR, CDTOTKVV_DIR, CDTOTKVV_COLS, CDTOTKVV_DATA_ROW_START
from config import PGD_DATA_DIR
from data.core import ts_file
from data.pgd import duong_dan_pgd

_COLS_FLOAT = ["du_no", "so_du_tk", "tong_diem"]
_COLS_STR   = ["ma_dv", "ma_xa", "ma_to"]
_CODE_WIDTHS = {"ma_dv": 6, "ma_xa": 6, "ma_to": 7}
_XEP_LOAI_TOT = "T\u1ed1t"
_XEP_LOAI_KHA = "Kh\u00e1"
_XEP_LOAI_TB  = "Trung b\u00ecnh"
_XEP_LOAI_YEU = "Y\u1ebfu"
_TINH_TRANG_A = "A"
_TINH_TRANG_B = "B"
_TINH_TRANG_C = "C"


def _norm_text_key(val) -> str:
    """Chuẩn hóa text header Excel để dò cột linh hoạt hơn."""
    if val is None:
        return ""
    text = unicodedata.normalize("NFKD", str(val))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("đ", "d").replace("Đ", "D").lower().strip()
    return "".join(ch for ch in text if ch.isalnum())


def _normalize_code_value(val, width: int | None = None):
    """Chuẩn hóa mã đọc từ Excel, giữ số 0 đầu cho các cột định danh."""
    if val is None or pd.isna(val):
        return pd.NA
    text = str(val).strip()
    if not text or text.lower() in {"nan", "none", "nat"}:
        return pd.NA
    text = re.sub(r"\.0+$", "", text)
    if width and re.fullmatch(r"\d+", text):
        return text.zfill(width)
    return text


def _tim_header_cdto_toan_cn(all_rows: list[list]) -> tuple[int | None, dict[str, int]]:
    """Tìm dòng header và map tên trường -> index cột trong file toàn CN."""
    alias_map = {
        "stt": {"stt"},
        "ma_dv": {"mapgd", "maphonggiaodich", "mapgd6so"},
        "ten_dv": {"tenpgd", "tendonvi", "tendv"},
        "ma_xa": {"maxa"},
        "ten_xa": {"tenxa"},
        "ma_to": {"mato"},
        "ten_to_truong": {"tento", "tentotruong"},
        "loai_to": {"loaito"},
        "dvut": {"dvut", "madvut", "tendvut"},
        "du_no": {"duno"},
        "tong_diem": {"tongdiem"},
        "xep_loai": {"xeploai"},
        "ngaybc": {"ngaybc", "ngaybaocao"},
    }
    for row_idx, row in enumerate(all_rows[:20]):
        idx_map: dict[str, int] = {}
        for col_idx, cell in enumerate(row):
            key = _norm_text_key(cell)
            if not key:
                continue
            for field, aliases in alias_map.items():
                if key in aliases and field not in idx_map:
                    idx_map[field] = col_idx
                    break
        if "stt" in idx_map and "ma_dv" in idx_map:
            return row_idx, idx_map
    return None, {}


def _chon_cot_ma_pgd_tot_nhat(
    all_rows: list[list],
    valid_codes: set[str],
    preferred_idx: int | None = None,
    start_row: int = 0,
) -> int | None:
    """Chọn cột có nhiều mã PGD hợp lệ/đa dạng nhất trong phần data."""

    def _norm_ma_local(val) -> str | None:
        if val is None:
            return None
        try:
            return str(int(float(str(val).strip()))).zfill(6)
        except (ValueError, TypeError):
            return None

    sample_rows = all_rows[start_row : start_row + 300]
    max_cols = max((len(r) for r in sample_rows), default=0)
    best_idx = None
    best_score = (-1, -1, -1)
    for col_idx in range(max_cols):
        hits = 0
        unique_codes: set[str] = set()
        for row in sample_rows:
            if len(row) <= col_idx:
                continue
            ma = _norm_ma_local(row[col_idx])
            if ma and ma in valid_codes:
                hits += 1
                unique_codes.add(ma)
        if not hits:
            continue
        score = (
            len(unique_codes),
            hits,
            1 if preferred_idx is not None and col_idx == preferred_idx else 0,
        )
        if score > best_score:
            best_score = score
            best_idx = col_idx
    return best_idx


def _ten_file(thang_nam: str) -> Path:
    return CDTOTKVV_DIR / f"CDTOTKVV_{thang_nam}.xlsx"


def doc_thang_nam_tu_file(file_bytes: bytes) -> str | None:
    """Trích kỳ chấm điểm mm/yyyy từ phần đầu file CDTOTKVV (tiêu đề / ngày báo cáo)."""
    from datetime import date, datetime
    from io import BytesIO

    import openpyxl

    pat_ngay_vn = re.compile(
        r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})",
        re.IGNORECASE,
    )
    pat_ddmmyyyy = re.compile(
        r"\b([0-2]?\d|3[0-1])[/\-]([0]?\d|1[0-2])[/\-](\d{4})\b"
    )
    pat_thang_slash_nam = re.compile(r"\b(0[1-9]|1[0-2])/\s*(\d{4})\b")
    pat_thang_word = re.compile(
        r"tháng\s*(\d{1,2})\s*/\s*(\d{4})",
        re.IGNORECASE,
    )
    try:
        wb = openpyxl.load_workbook(
            BytesIO(file_bytes), read_only=True, data_only=True
        )
        ws = wb.active
        cap = min(ws.max_row or 0, 25)
        for row in ws.iter_rows(min_row=1, max_row=cap, values_only=True):
            for cell in row:
                if cell is None:
                    continue
                if isinstance(cell, (datetime, date)):
                    return cell.strftime("%m/%Y")
                text = str(cell).strip()
                if not text or text.lower() == "nan":
                    continue
                m = pat_ngay_vn.search(text)
                if m:
                    mm = m.group(2).zfill(2)
                    yyyy = m.group(3)
                    return f"{mm}/{yyyy}"
                m = pat_thang_word.search(text)
                if m:
                    return f"{m.group(1).zfill(2)}/{m.group(2)}"
                m = pat_thang_slash_nam.search(text)
                if m:
                    return f"{m.group(1)}/{m.group(2)}"
                m = pat_ddmmyyyy.search(text)
                if m:
                    mm = m.group(2).zfill(2)
                    yyyy = m.group(3)
                    return f"{mm}/{yyyy}"
    except Exception:
        return None
    return None


@st.cache_data(show_spinner=False)
def doc_cdtotkvv_path(duong_dan: str, _ts) -> pd.DataFrame | None:
    if not duong_dan or not os.path.exists(duong_dan):
        return None
    df = pd.read_excel(
        duong_dan,
        engine="openpyxl",
        header=None,
        skiprows=CDTOTKVV_DATA_ROW_START,
    )
    if df.empty:
        return None
    df = df.iloc[:, : len(CDTOTKVV_COLS)].copy()
    # File tách từ toàn CN: openpyxl bỏ trailing None → có thể thiếu cột cuối (tinh_trang)
    for col in CDTOTKVV_COLS[len(df.columns):]:
        df[col] = pd.NA
    df.columns = CDTOTKVV_COLS
    df = df[pd.to_numeric(df["stt"], errors="coerce").notna()].reset_index(drop=True)
    for col in _COLS_FLOAT:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in _COLS_STR:
        if col in df.columns:
            width = _CODE_WIDTHS.get(col)
            df[col] = df[col].map(lambda v, w=width: _normalize_code_value(v, w))
    return df


@st.cache_data(show_spinner=False)
def doc_cdtotkvv(thang_nam: str) -> pd.DataFrame | None:
    try:
        mm, yyyy = thang_nam.split("/")
        suffix = f"{yyyy}_{mm}"
    except ValueError:
        return None
    pgd_data = BASE_DIR / "pgd_data"
    frames = []
    for f in pgd_data.rglob(f"cdtotkvv_{suffix}.xlsx"):
        df = doc_cdtotkvv_path(str(f), ts_file(str(f)))
        if df is not None and not df.empty:
            frames.append(df)
    if not frames:
        for f in pgd_data.rglob("cdtotkvv_latest.xlsx"):
            try:
                thang = doc_thang_nam_tu_file(f.read_bytes())
                if thang == thang_nam:
                    df = doc_cdtotkvv_path(str(f), ts_file(str(f)))
                    if df is not None and not df.empty:
                        frames.append(df)
            except Exception:
                pass
    if not frames:
        return None
    return pd.concat(frames, ignore_index=True)


@st.cache_data(show_spinner=False)
def doc_cdtotkvv_pgd(ten_pgd: str, _ts) -> pd.DataFrame | None:
    path = duong_dan_pgd(ten_pgd, "cdtotkvv")
    return doc_cdtotkvv_path(path, _ts)


def doc_cdtotkvv_toan_cn_pgd() -> pd.DataFrame | None:
    if not os.path.exists(PGD_DATA_DIR):
        return None
    frames: list[pd.DataFrame] = []
    for d in sorted(Path(PGD_DATA_DIR).iterdir()):
        if not d.is_dir():
            continue
        path = d / "cdtotkvv_latest.xlsx"
        if not path.exists():
            continue
        try:
            df_p = doc_cdtotkvv_path(str(path), ts_file(str(path)))
            if df_p is None or df_p.empty:
                continue
            frames.append(df_p)
        except Exception:
            continue
    if not frames:
        return None
    return pd.concat(frames, ignore_index=True)


@st.cache_data(show_spinner=False)
def tong_hop_tu_pgd_data() -> pd.DataFrame | None:
    """Tổng hợp CDTOTKVV từ pgd_data/*/cdtotkvv_latest.xlsx (hệ thống tập trung)."""
    return doc_cdtotkvv_toan_cn_pgd()


@st.cache_data(show_spinner=False)
def ds_thang_nam() -> list[str]:
    pat = re.compile(r"cdtotkvv_(\d{4})_(\d{2})\.xlsx$", re.IGNORECASE)
    thang_set = set()
    pgd_data = BASE_DIR / "pgd_data"
    if not pgd_data.exists():
        return []
    for f in pgd_data.rglob("cdtotkvv_*.xlsx"):
        m = pat.search(f.name)
        if m:
            yyyy, mm = m.group(1), m.group(2)
            thang_set.add(f"{mm}/{yyyy}")
    for f in pgd_data.rglob("cdtotkvv_latest.xlsx"):
        try:
            thang = doc_thang_nam_tu_file(f.read_bytes())
            if thang:
                thang_set.add(thang)
        except Exception:
            pass
    return sorted(thang_set, key=lambda s: (s[3:], s[:2]), reverse=True)


def doc_thang_tu_cdto_toan_cn(file_bytes: bytes) -> str | None:
    """
    Đọc tháng báo cáo từ cột NGAYBC (cột S, index 18) của file CDTOTKVV toàn CN.
    Đáng tin hơn doc_thang_nam_tu_file() vì đọc từ dữ liệu thực (không bị
    ảnh hưởng bởi ngày tạo/export file trong header).
    Trả về "MM/YYYY" hoặc None nếu không đọc được.
    """
    from io import BytesIO
    from datetime import datetime, date as _date

    import openpyxl

    from config import MA_PGD_MAP

    def _norm_ma(val) -> str | None:
        try:
            return str(int(float(str(val).strip()))).zfill(6)
        except (ValueError, TypeError):
            return None

    try:
        wb = openpyxl.load_workbook(BytesIO(file_bytes), read_only=True, data_only=True)
        ws = wb.active
        all_rows = [list(r) for r in ws.iter_rows(values_only=True)]
        wb.close()
        _header_row, idx_map = _tim_header_cdto_toan_cn(all_rows)
        col_mapgd = _chon_cot_ma_pgd_tot_nhat(
            all_rows,
            set(MA_PGD_MAP),
            preferred_idx=idx_map.get("ma_dv"),
            start_row=(_header_row or 0) + 1,
        )
        col_ngaybc = idx_map.get("ngaybc")

        for row in all_rows:
            row = list(row)
            if col_mapgd is None:
                ma_dv = next(
                    (
                        ma
                        for idx in (2, 1)
                        if len(row) > idx
                        for ma in [_norm_ma(row[idx])]
                        if ma and ma in MA_PGD_MAP
                    ),
                    None,
                )
            else:
                if len(row) <= col_mapgd:
                    continue
                ma_dv = _norm_ma(row[col_mapgd])
            if not ma_dv or ma_dv not in MA_PGD_MAP:
                continue
            if col_ngaybc is None:
                val = next((row[idx] for idx in (18, 17) if len(row) > idx), None)
            else:
                if len(row) <= col_ngaybc:
                    break
                val = row[col_ngaybc]
            if val is None:
                break
            if isinstance(val, (datetime, _date)):
                return val.strftime("%m/%Y")
            if val:
                m = re.search(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})", str(val).strip())
                if m:
                    return f"{m.group(2).zfill(2)}/{m.group(3)}"
            break
    except Exception:
        pass
    return None


def tach_file_cdto_toan_cn(file_bytes: bytes) -> dict[str, bytes]:
    """
    Đọc file CDTOTKVV toàn CN, tách thành dict {ten_pgd: excel_bytes}.
    Mỗi file con được chuẩn hóa theo đúng CDTOTKVV_COLS (20 cột per-PGD)
    để doc_cdtotkvv_path() đọc được chính xác.

    Format toàn CN (18 cột):
      0:STT 1:MAPGD 2:TEN_PGD 3:MAXA 4:TENXA 5:MATO 6:TENTO
      7:LOAITO 8:DVUT 9:DUNO 10:Tham gia GDX 11:TL thu nợ gốc
      12:TL thu lãi 13:TG Tổ TKVV 14:TL nợ quá hạn
      15:TONGDIEM 16:XEPLOAI 17:NGAYBC

    Format per-PGD / CDTOTKVV_COLS (20 cột):
      0:stt 1:ma_dv 2:ten_dv 3:ma_xa 4:ten_xa 5:ma_to
      6:ten_to_truong 7:dvut 8:loai_to 9:du_no 10:so_du_tk
      11-16:diem_* 17:tong_diem 18:xep_loai 19:tinh_trang

    Raises ValueError nếu không đọc được hoặc không tìm thấy đơn vị hợp lệ.
    """
    from io import BytesIO
    from collections import defaultdict

    import openpyxl

    from config import MA_PGD_MAP, CDTOTKVV_DATA_ROW_START

    # Số cột đầu ra cố định theo CDTOTKVV_COLS
    N_COLS_OUT = 20
    FALLBACK_IDX = {
        "stt": 1,
        "ma_dv": 2,
        "ten_dv": 3,
        "ma_xa": 4,
        "ten_xa": 5,
        "ma_to": 6,
        "ten_to_truong": 7,
        "loai_to": 8,
        "dvut": 9,
        "du_no": 10,
        "tong_diem": 16,
        "xep_loai": 17,
    }

    def _norm_ma(val) -> str | None:
        if val is None:
            return None
        try:
            return str(int(float(str(val).strip()))).zfill(6)
        except (ValueError, TypeError):
            return None

    def _get(row: list, idx: int):
        return row[idx] if idx < len(row) else None

    def _src(row: list, field: str):
        idx = idx_map.get(field, FALLBACK_IDX.get(field))
        if idx is None:
            return None
        return _get(row, idx)

    def _map_row(src: list) -> list:
        """Chuyển 1 data row từ format toàn CN → CDTOTKVV_COLS (20 cột)."""
        return [
            _src(src, "stt"),
            _src(src, "ma_dv"),
            _src(src, "ten_dv"),
            _src(src, "ma_xa"),
            _src(src, "ten_xa"),
            _src(src, "ma_to"),
            _src(src, "ten_to_truong"),
            _src(src, "dvut"),
            _src(src, "loai_to"),
            _src(src, "du_no"),
            None,           # so_du_tk     (không có trong toàn CN)
            None,           # diem_gdtx    (không có)
            None,           # diem_nqh     (không có)
            None,           # diem_thu_no  (không có)
            None,           # diem_thu_lai (không có)
            None,           # diem_tv_tiengui (không có)
            None,           # diem_ds_tg   (không có)
            _src(src, "tong_diem"),
            _src(src, "xep_loai"),
            None,           # tinh_trang   (không có trong toàn CN)
        ]

    # Tự phát hiện dòng bắt đầu dữ liệu: dòng đầu tiên có MAPGD hợp lệ
    # (đáng tin hơn STT vì MAPGD là cột ta cần, header sẽ không có mã 6 số)
    wb = openpyxl.load_workbook(BytesIO(file_bytes), read_only=True, data_only=True)
    ws = wb.active
    all_rows = [list(r) for r in ws.iter_rows(values_only=True)]
    wb.close()
    _header_row, idx_map = _tim_header_cdto_toan_cn(all_rows)
    col_ma_dv_in = _chon_cot_ma_pgd_tot_nhat(
        all_rows,
        set(MA_PGD_MAP),
        preferred_idx=idx_map.get("ma_dv", FALLBACK_IDX["ma_dv"]),
        start_row=(_header_row or 0) + 1,
    )
    if col_ma_dv_in is None:
        col_ma_dv_in = idx_map.get("ma_dv", FALLBACK_IDX["ma_dv"])
    idx_map["ma_dv"] = col_ma_dv_in

    data_start = None
    for i, row in enumerate(all_rows):
        if not row or len(row) <= col_ma_dv_in:
            continue
        ma_dv = _norm_ma(row[col_ma_dv_in])
        if ma_dv and ma_dv in MA_PGD_MAP:
            data_start = i
            break

    if data_start is None:
        raise ValueError(
            "Không tìm thấy dòng dữ liệu hợp lệ trong file "
            "(cột 'Mã PGD' phải chứa mã 6 số như 004601, 004602…)"
        )

    raw_headers = all_rows[:data_start]
    data_rows   = all_rows[data_start:]

    # Đảm bảo đúng CDTOTKVV_DATA_ROW_START dòng header để
    # doc_cdtotkvv_path(skiprows=CDTOTKVV_DATA_ROW_START) đọc không lệch.
    empty_row = [None] * N_COLS_OUT
    header_rows = raw_headers[:CDTOTKVV_DATA_ROW_START]
    while len(header_rows) < CDTOTKVV_DATA_ROW_START:
        header_rows.append(empty_row)

    groups: dict[str, list] = defaultdict(list)
    for row in data_rows:
        if not row or len(row) <= col_ma_dv_in:
            continue
        ma_dv = _norm_ma(row[col_ma_dv_in])
        if ma_dv and ma_dv in MA_PGD_MAP:
            groups[ma_dv].append(row)

    if not groups:
        raise ValueError(
            "Không tìm thấy mã đơn vị hợp lệ trong file "
            "(kiểm tra cột 'Mã PGD' có giá trị 6 chữ số như 004601)"
        )

    result: dict[str, bytes] = {}
    for ma_dv, rows in groups.items():
        ten_pgd = MA_PGD_MAP[ma_dv]
        wb_out  = openpyxl.Workbook(write_only=True)
        ws_out  = wb_out.create_sheet()

        # Ghi header gốc (metadata, bị skip khi đọc)
        for hrow in header_rows:
            ws_out.append(hrow + [None] * max(0, N_COLS_OUT - len(hrow)))

        # Ghi data rows đã chuẩn hóa theo CDTOTKVV_COLS
        for drow in rows:
            ws_out.append(_map_row(drow))

        buf = BytesIO()
        wb_out.save(buf)
        result[ten_pgd] = buf.getvalue()

    return result


@st.cache_data(show_spinner=False)
def tong_hop_theo_pgd(df: pd.DataFrame) -> pd.DataFrame:
    """
    Nhóm theo ma_dv + ten_dv, tính:
    - tong_to           : tổng số tổ
    - tong_diem_tb      : trung bình tổng_diem (làm tròn 2 chữ số)
    - to_tot/kha/tb/yeu : số tổ theo xep_loai
    - to_tinh_trang_a/b/c : số tổ theo tình trạng A/B/C
    Trả về DataFrame sort theo ma_dv.
    """
    nhom = df.groupby(["ma_dv", "ten_dv"], as_index=False)
    tong_hop = nhom.agg(
        tong_to=("stt", "count"),
        tong_diem_tb=("tong_diem", "mean"),
    )
    for ten_col, gia_tri in [
        ("to_tot", _XEP_LOAI_TOT),
        ("to_kha", _XEP_LOAI_KHA),
        ("to_tb",  _XEP_LOAI_TB),
        ("to_yeu", _XEP_LOAI_YEU),
    ]:
        dem = (
            df[df["xep_loai"] == gia_tri]
            .groupby(["ma_dv", "ten_dv"], as_index=False)
            .agg(**{ten_col: ("stt", "count")})
        )
        tong_hop = tong_hop.merge(dem, on=["ma_dv", "ten_dv"], how="left")
    for ten_col, gia_tri in [
        ("to_tinh_trang_a", _TINH_TRANG_A),
        ("to_tinh_trang_b", _TINH_TRANG_B),
        ("to_tinh_trang_c", _TINH_TRANG_C),
    ]:
        dem = (
            df[df["tinh_trang"] == gia_tri]
            .groupby(["ma_dv", "ten_dv"], as_index=False)
            .agg(**{ten_col: ("stt", "count")})
        )
        tong_hop = tong_hop.merge(dem, on=["ma_dv", "ten_dv"], how="left")
    cols_dem = [
        "to_tot", "to_kha", "to_tb", "to_yeu",
        "to_tinh_trang_a", "to_tinh_trang_b", "to_tinh_trang_c",
    ]
    tong_hop[cols_dem] = tong_hop[cols_dem].fillna(0).astype(int)
    tong_hop["tong_diem_tb"] = tong_hop["tong_diem_tb"].round(2)
    return tong_hop.sort_values("ma_dv").reset_index(drop=True)
