"""
Nhận diện loại file và tên đơn vị từ nội dung file Excel.
Tách từ tab_upload_khnv.py — không phụ thuộc Streamlit.
Dùng bởi: tab_upload_khnv.py (form upload đơn lẻ + import hàng loạt).
"""
from __future__ import annotations

import hashlib
from io import BytesIO

import pandas as pd

from config import DON_VI_CHI_NHANH, DS_PGD, MA_PGD_MAP

# ── Constants ────────────────────────────────────────────────────────────────

DS_DON_VI: list[str] = [DON_VI_CHI_NHANH] + DS_PGD

# Bảng alias tên đơn vị: tên trong file Excel → tên nội bộ hệ thống
# Dùng để so sánh "upload nhầm đơn vị" không bị lỗi do tên khác nhau
# "PGD Biên Hòa" là alias — trong HSTD tên thực là "Hội sở Chi nhánh tỉnh"
TEN_DV_ALIAS: dict[str, str] = {
    "Hội sở CN Đồng Nai":      DON_VI_CHI_NHANH,
    "Hội sở CN tỉnh":          DON_VI_CHI_NHANH,
    "CN Đồng Nai":             DON_VI_CHI_NHANH,
    "PGD Biên Hòa":            DON_VI_CHI_NHANH,
    # Thêm alias khác nếu phát sinh
}


# ── MD5 checksum helpers ─────────────────────────────────────────────────────

def md5_bytes(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def md5_file(path: str) -> str:
    try:
        return hashlib.md5(open(path, "rb").read()).hexdigest()
    except Exception:  # conv: skip — file not found is expected
        return ""


# ── Chuẩn hóa tên đơn vị ────────────────────────────────────────────────────

def chuan_hoa_ten(ten: str) -> str:
    """Chuẩn hóa tên đơn vị từ file về tên nội bộ (tra TEN_DV_ALIAS, fallback giữ nguyên)."""
    return TEN_DV_ALIAS.get(ten.strip(), ten.strip())


def ten_doc_ve_don_vi_chuan(val: str) -> str | None:
    """Map tên đọc từ file → đúng một phần tử trong DS_DON_VI."""
    if not val or str(val).strip().lower() in ("nan", "none", ""):
        return None
    t = chuan_hoa_ten(str(val).strip())
    if t in DS_DON_VI:
        return t
    tl = t.lower()
    for ten_dv in DS_DON_VI:
        if ten_dv.lower() in tl:
            return ten_dv
    return None


# ── Đọc tên đơn vị từ file upload ───────────────────────────────────────────

def lay_ten_don_vi_trong_file(file_bytes: bytes, loai: str) -> str | None:
    """
    Đọc tên đơn vị từ file Excel theo từng loại.
    Trả về tên đơn vị (str) hoặc None nếu không đọc được.

    HSTD/GQVL : header=4, cột "Tên PGD" (sheet BCQUERY / Sheet1)
    NQ11       : header=4, cột "Mã PGD" → tra MA_PGD_MAP
    CDTOTKVV   : header=7, dropna("Mã đơn vị"), cột "Tên đơn vị"
    """
    try:
        buf = BytesIO(file_bytes)
        if loai == "hstd":
            df = pd.read_excel(buf, sheet_name="BCQUERY", header=4, nrows=5)
            df = df.iloc[:, 1:]
            cot = next((c for c in df.columns if "tên pgd" in str(c).lower()), None)
            if cot is None:
                return None
            vals = df[cot].dropna().astype(str).unique()
            return str(vals[0]).strip() if len(vals) > 0 else None

        elif loai == "nq11":
            df = pd.read_excel(buf, sheet_name="BCQUERY", header=4, nrows=5)
            df = df.iloc[:, 1:]
            cot = next((c for c in df.columns if "mã pgd" in str(c).lower()), None)
            if cot is None:
                return None
            raw = df[cot].dropna().iloc[0] if not df[cot].dropna().empty else None
            if raw is None:
                ma_pgd = None
            else:
                try:
                    # Xử lý trường hợp pandas đọc ô số dạng float (vd: 4602.0 → "004602")
                    ma_pgd = str(int(float(raw))).zfill(6)
                except (ValueError, TypeError):
                    ma_pgd = str(raw).strip().zfill(6)
            if ma_pgd is None:
                return None
            return MA_PGD_MAP.get(ma_pgd)

        elif loai == "gqvl":
            df = pd.read_excel(buf, sheet_name="Sheet1", header=4, nrows=5)
            df = df.iloc[:, 1:]
            cot = next((c for c in df.columns if "tên pgd" in str(c).lower()), None)
            if cot is None:
                return None
            vals = df[cot].dropna().astype(str).unique()
            return str(vals[0]).strip() if len(vals) > 0 else None

        elif loai == "cdtotkvv":
            df = pd.read_excel(buf, header=7, nrows=10)
            # Tìm cột "Mã đơn vị"
            cot_ma = next((c for c in df.columns if "mã đơn vị" in str(c).lower()), None)
            cot_ten = next((c for c in df.columns if "tên đơn vị" in str(c).lower()), None)
            if cot_ten is None:
                return None
            if cot_ma is not None:
                df = df.dropna(subset=[cot_ma])
            vals = df[cot_ten].dropna().astype(str).unique()
            return str(vals[0]).strip() if len(vals) > 0 else None

    except Exception:  # conv: skip — unrecognized format fallback
        return None


def kiem_tra_don_vi(file_bytes: bytes, loai: str, ten_dv_chon: str) -> tuple[bool, str]:
    """
    Kiểm tra tên đơn vị trong file có khớp với đơn vị đang chọn không.
    Trả về (khop: bool, thong_bao: str).
    """
    ten_trong_file = lay_ten_don_vi_trong_file(file_bytes, loai)
    if ten_trong_file is None:
        return True, "⚠️ Không đọc được tên đơn vị từ file — tiếp tục lưu."
    if chuan_hoa_ten(ten_trong_file) == chuan_hoa_ten(ten_dv_chon):
        return True, f"✅ Đơn vị khớp: **{chuan_hoa_ten(ten_trong_file)}**"
    return False, (
        f"⚠️ Upload nhầm đơn vị! File chứa: **{ten_trong_file}** | Đang chọn: **{ten_dv_chon}**"
    )


# ── Nhận diện loại file từ nội dung ─────────────────────────────────────────

def nhan_dien_loai_tu_noi_dung(data: bytes) -> str | None:
    """
    Nhận diện loại file từ nội dung — không phụ thuộc tên file.
      HSTD     : sheet BCQUERY, header row 5 có cột 'Tên PGD'
      NQ11     : sheet BCQUERY, header row 5 không có 'Tên PGD', có 'Mã ĐVUT'
      GQVL     : không có BCQUERY, có Sheet1
      CDTOTKVV : không có BCQUERY, không có Sheet1,
                 row 10 có cột 'stt' + 'ma_dv' + 'tong_diem'
    """
    try:
        xl = pd.ExcelFile(BytesIO(data))
        sheets_upper = [s.upper() for s in xl.sheet_names]

        # ── HSTD hoặc NQ11 ───────────────────────────────────────────
        if "BCQUERY" in sheets_upper:
            real = xl.sheet_names[sheets_upper.index("BCQUERY")]
            df = pd.read_excel(
                BytesIO(data), sheet_name=real, header=4, nrows=1
            )
            cols = [str(c).strip().lower() for c in df.columns]
            if any("tên pgd" in c for c in cols):
                return "hstd"
            if any(
                "mã đvut" in c or "mã dvut" in c or "tến đvut" in c for c in cols
            ):
                return "nq11"
            # Fallback: BCQUERY nhưng không rõ → coi là NQ11
            return "nq11"

        # ── GQVL / CDTOTKVV ───────────────────────────────────────────
        if "SHEET1" in sheets_upper or any(
            s for s in sheets_upper
            if s not in ("BCQUERY",) and not s.startswith("_")
        ):
            try:
                if "SHEET1" in sheets_upper:
                    real = xl.sheet_names[sheets_upper.index("SHEET1")]
                    df_check = pd.read_excel(
                        BytesIO(data), sheet_name=real,
                        header=7, nrows=1
                    )
                    cols_check = [str(c).strip().lower() for c in df_check.columns]
                    if any("tên đơn vị" in c for c in cols_check):
                        return "cdtotkvv"
                    if any("tên pgd" in c for c in cols_check):
                        return "gqvl"
                    return "gqvl"

                real = xl.sheet_names[0]
                df_check = pd.read_excel(
                    BytesIO(data), sheet_name=real,
                    header=7, nrows=2
                )
                cols_check = [str(c).strip().lower() for c in df_check.columns]
                if any(
                    "khế ước" in c or "khe uoc" in c
                    or "dư nợ" in c or "du no" in c
                    or "mã kh" in c
                    for c in cols_check
                ):
                    return "gqvl"
            except Exception:  # conv: skip — detection probe, failure is expected
                pass

        # ── CDTOTKVV ─────────────────────────────────────────────────
        df2 = pd.read_excel(BytesIO(data), header=None, skiprows=9, nrows=2)
        if not df2.empty:
            vals = [
                str(v).strip().lower()
                for v in df2.iloc[0].tolist()
                if pd.notna(v)
            ]
            if any("stt" in v for v in vals) and any(
                "ma_dv" in v or "mã" in v for v in vals
            ):
                return "cdtotkvv"

    except Exception:
        pass
    return None


def tim_ten_pgd_tu_noi_dung(file_bytes: bytes, loai: str) -> str | None:
    """
    Đọc tối thiểu nội dung file để nhận diện tên PGD (quét thư mục / import hàng loạt).

    HSTD/NQ11: sheet BCQUERY, header ở dòng 5 (pandas header=4), 1 dòng dữ liệu, cột "Tên PGD".
    GQVL: Sheet1, header=7 (khớp data/hstd.doc_file_gqvl).
    CDTOTKVV: quét tối đa 15 dòng đầu (layout không cố định).
    """
    buf = BytesIO(file_bytes)
    try:
        if loai in ("hstd", "nq11"):
            df = None
            try:
                df = pd.read_excel(
                    buf,
                    sheet_name="BCQUERY",
                    header=4,
                    nrows=1,
                    usecols=["Tên PGD"],
                )
            except (ValueError, KeyError):
                buf.seek(0)
                df_wide = pd.read_excel(
                    buf, sheet_name="BCQUERY", header=4, nrows=5
                ).iloc[:, 1:]
                cot = next(
                    (c for c in df_wide.columns if "tên pgd" in str(c).lower()),
                    None,
                )
                if cot is not None:
                    df = df_wide[[cot]].head(1)

            if df is not None and not df.empty:
                col = df.columns[0]
                raw = str(df[col].iloc[0]).strip()
                hit = ten_doc_ve_don_vi_chuan(raw)
                if hit:
                    return hit

            if loai == "nq11":
                buf.seek(0)
                df_m = pd.read_excel(
                    buf, sheet_name="BCQUERY", header=4, nrows=5
                ).iloc[:, 1:]
                cot_ma = next(
                    (c for c in df_m.columns if "mã pgd" in str(c).lower()),
                    None,
                )
                if cot_ma is not None and not df_m[cot_ma].dropna().empty:
                    ma_pgd = str(df_m[cot_ma].dropna().iloc[0]).strip().zfill(6)
                    ten_ma = MA_PGD_MAP.get(ma_pgd)
                    if ten_ma and ten_ma in DS_DON_VI:
                        return ten_ma
            return None

        if loai == "gqvl":
            df = pd.read_excel(buf, sheet_name="Sheet1", header=7, nrows=10)
            if df.empty:
                return None

            cot_ma = next(
                (
                    c
                    for c in df.columns
                    if "mã đơn vị" in str(c).strip().lower()
                    or "ma don vi" in str(c).strip().lower()
                ),
                None,
            )
            if cot_ma is None:
                cot_ma = df.columns[1] if len(df.columns) > 1 else df.columns[0]

            s = df[cot_ma].dropna()
            if s.empty:
                return None

            raw = s.iloc[0]
            try:
                ma = str(int(float(raw))).zfill(6)
            except Exception:  # conv: skip — string fallback for non-numeric cell
                ma = str(raw).strip()
                digits = "".join(ch for ch in ma if ch.isdigit())
                if digits:
                    ma = digits.zfill(6)

            ten_ma = MA_PGD_MAP.get(ma)
            if ten_ma and ten_ma in DS_DON_VI:
                return ten_ma
            return ten_ma

        if loai == "cdtotkvv":
            df = pd.read_excel(buf, header=None, nrows=15)
            for _, row in df.iterrows():
                for cell in row:
                    if cell is None or (isinstance(cell, float) and pd.isna(cell)):
                        continue
                    hit = ten_doc_ve_don_vi_chuan(str(cell).strip())
                    if hit:
                        return hit
            return None

    except Exception:  # conv: skip — detection probe, failure is expected
        return None
    return None
