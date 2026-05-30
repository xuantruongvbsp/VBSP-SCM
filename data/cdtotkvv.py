"""Đọc và tổng hợp dữ liệu Chấm điểm Tổ TK&VV (CDTOTKVV)."""
import re
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from config import BASE_DIR, CDTOTKVV_DIR, CDTOTKVV_COLS, CDTOTKVV_DATA_ROW_START
from config import PGD_DATA_DIR
from data.core import ts_file
from data.pgd import duong_dan_pgd

_COLS_FLOAT = ["du_no", "so_du_tk", "tong_diem"]
_COLS_STR   = ["ma_dv", "ma_xa", "ma_to"]
_XEP_LOAI_TOT = "T\u1ed1t"
_XEP_LOAI_KHA = "Kh\u00e1"
_XEP_LOAI_TB  = "Trung b\u00ecnh"
_XEP_LOAI_YEU = "Y\u1ebfu"
_TINH_TRANG_A = "A"
_TINH_TRANG_B = "B"
_TINH_TRANG_C = "C"


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
            df[col] = (
                df[col]
                .astype(str)
                .str.strip()
                .str.replace(r"\.0$", "", regex=True)
                .replace("nan", pd.NA)
            )
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

    COL_MAPGD  = 2   # cột C
    COL_NGAYBC = 18  # cột S

    def _norm_ma(val) -> str | None:
        try:
            return str(int(float(str(val).strip()))).zfill(6)
        except (ValueError, TypeError):
            return None

    try:
        wb = openpyxl.load_workbook(BytesIO(file_bytes), read_only=True, data_only=True)
        ws = wb.active
        for row in ws.iter_rows(values_only=True):
            row = list(row)
            if len(row) <= COL_MAPGD:
                continue
            ma_dv = _norm_ma(row[COL_MAPGD])
            if not ma_dv or ma_dv not in MA_PGD_MAP:
                continue
            # Dòng data hợp lệ — đọc NGAYBC
            if len(row) <= COL_NGAYBC:
                break
            val = row[COL_NGAYBC]
            if isinstance(val, (datetime, _date)):
                return val.strftime("%m/%Y")
            if val:
                m = re.search(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})", str(val).strip())
                if m:
                    return f"{m.group(2).zfill(2)}/{m.group(3)}"
            break
        wb.close()
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
    # Vị trí cột MAPGD trong file toàn CN — cột A trống, data bắt đầu từ cột B
    # nên: B=STT(1), C=MAPGD(2), D=TEN_PGD(3), ...
    COL_MA_DV_IN = 2

    def _norm_ma(val) -> str | None:
        if val is None:
            return None
        try:
            return str(int(float(str(val).strip()))).zfill(6)
        except (ValueError, TypeError):
            return None

    def _get(row: list, idx: int):
        return row[idx] if idx < len(row) else None

    def _map_row(src: list) -> list:
        """Chuyển 1 data row từ format toàn CN → CDTOTKVV_COLS (20 cột).
        Cột A trống nên index lệch +1 so với tên cột:
          B(1)=STT  C(2)=MAPGD  D(3)=TEN_PGD  E(4)=MAXA  F(5)=TENXA
          G(6)=MATO  H(7)=TENTO  I(8)=LOAITO  J(9)=DVUT  K(10)=DUNO
          L(11)=Tham gia GDX  ...  Q(16)=TONGDIEM  R(17)=XEPLOAI  S(18)=NGAYBC
        """
        return [
            _get(src,  1),  # stt          ← B: STT
            _get(src,  2),  # ma_dv        ← C: MAPGD
            _get(src,  3),  # ten_dv       ← D: TEN_PGD
            _get(src,  4),  # ma_xa        ← E: MAXA
            _get(src,  5),  # ten_xa       ← F: TENXA
            _get(src,  6),  # ma_to        ← G: MATO
            _get(src,  7),  # ten_to_truong← H: TENTO
            _get(src,  9),  # dvut         ← J: DVUT  (đổi chỗ với LOAITO)
            _get(src,  8),  # loai_to      ← I: LOAITO (đổi chỗ với DVUT)
            _get(src, 10),  # du_no        ← K: DUNO
            None,           # so_du_tk     (không có trong toàn CN)
            None,           # diem_gdtx    (không có)
            None,           # diem_nqh     (không có)
            None,           # diem_thu_no  (không có)
            None,           # diem_thu_lai (không có)
            None,           # diem_tv_tiengui (không có)
            None,           # diem_ds_tg   (không có)
            _get(src, 16),  # tong_diem    ← Q: TONGDIEM
            _get(src, 17),  # xep_loai     ← R: XEPLOAI
            None,           # tinh_trang   (không có trong toàn CN)
        ]

    # Tự phát hiện dòng bắt đầu dữ liệu: dòng đầu tiên có MAPGD hợp lệ
    # (đáng tin hơn STT vì MAPGD là cột ta cần, header sẽ không có mã 6 số)
    wb = openpyxl.load_workbook(BytesIO(file_bytes), read_only=True, data_only=True)
    ws = wb.active
    all_rows = [list(r) for r in ws.iter_rows(values_only=True)]
    wb.close()

    data_start = None
    for i, row in enumerate(all_rows):
        if not row or len(row) <= COL_MA_DV_IN:
            continue
        ma_dv = _norm_ma(row[COL_MA_DV_IN])
        if ma_dv and ma_dv in MA_PGD_MAP:
            data_start = i
            break

    if data_start is None:
        raise ValueError(
            "Không tìm thấy dòng dữ liệu hợp lệ trong file "
            "(cột B 'Mã PGD' phải chứa mã 6 số như 004601, 004602…)"
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
        if not row or len(row) <= COL_MA_DV_IN:
            continue
        ma_dv = _norm_ma(row[COL_MA_DV_IN])
        if ma_dv and ma_dv in MA_PGD_MAP:
            groups[ma_dv].append(row)

    if not groups:
        raise ValueError(
            "Không tìm thấy mã đơn vị hợp lệ trong file "
            "(kiểm tra cột B 'Mã PGD' có giá trị 6 chữ số như 004601)"
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
