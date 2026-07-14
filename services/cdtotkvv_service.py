"""
Các hàm xử lý dữ liệu thuần (không có st.*) cho tab Chấm điểm Tổ TK&VV.

Extract từ tabs/tab_cdtotkvv.py để tái sử dụng và kiểm thử độc lập.
"""
from __future__ import annotations

import os

import pandas as pd

from config import (
    DS_PGD,
    DON_VI_CHI_NHANH,
)
from data.pgd import duong_dan_pgd as _duong_dan_pgd
from data.core import ts_file
from utils import fmt_so
try:
    from logger import get_logger
    logger = get_logger(__name__)
except Exception as e:
    logger.error("Lỗi trong khối except: %s", e, exc_info=True)
    import logging
    logger = logging.getLogger(__name__)


def tong_hop_tu_pgd_data() -> "pd.DataFrame | None":
    """Đọc cdtotkvv_latest.xlsx từ pgd_data/{slug}/ của tất cả đơn vị, concat lại."""
    from data.cdtotkvv import doc_cdtotkvv_path

    tat_ca_dv = [DON_VI_CHI_NHANH] + DS_PGD
    frames = []
    for ten_dv in tat_ca_dv:
        try:
            dd = _duong_dan_pgd(ten_dv, "cdtotkvv")
            if not dd or not os.path.exists(dd):
                continue
            df = doc_cdtotkvv_path(dd, ts_file(dd))
            if df is None:
                continue
            if not df.empty:
                frames.append(df)
        except Exception as e:
            logger.warning("tong_hop_tu_pgd_data: bỏ qua đơn vị lỗi — %s", e, exc_info=True)
            continue
    return pd.concat(frames, ignore_index=True) if frames else None


def bang_trang_thai_cdtotkvv() -> pd.DataFrame:
    """
    Tạo bảng trạng thái CDTOTKVV cho 22 đơn vị (Chi nhánh + 21 PGD).
    Trả về DataFrame với cột: Đơn vị, Trạng thái, Cập nhật lần cuối.
    """
    from data.pgd import doc_trang_thai_file

    tat_ca_dv = [DON_VI_CHI_NHANH] + DS_PGD

    rows = []
    for ten_dv in tat_ca_dv:
        trang_thai_info = doc_trang_thai_file(ten_dv, "cdtotkvv")

        if not trang_thai_info["co_file"]:
            trang_thai = "❌ Chưa có"
            cap_nhat = "—"
        else:
            ngay_upload = trang_thai_info["ngay_upload"]
            so_ngay_cu = trang_thai_info["so_ngay_cu"]

            if trang_thai_info["canh_bao"] == "ok":
                trang_thai = f"✅ {ngay_upload.strftime('%d/%m')}"
            else:
                trang_thai = f"⚠️ {ngay_upload.strftime('%d/%m')} ({so_ngay_cu} ngày)"

            cap_nhat = ngay_upload.strftime('%d/%m/%Y %H:%M')

        rows.append({
            "Đơn vị": ten_dv,
            "Trạng thái": trang_thai,
            "Cập nhật lần cuối": cap_nhat,
        })

    return pd.DataFrame(rows)


def loc_df(df: pd.DataFrame, mode: str, pgd_user: str) -> pd.DataFrame:
    """
    Lọc dữ liệu theo chế độ hiển thị:
    - mode "cn": toàn Chi nhánh (dùng cho ws_management)
    - mode "pgd": chỉ PGD mình (dùng cho ws_operation)
    """
    if df is None or df.empty:
        return df
    if mode == "pgd" and pgd_user:
        if "ma_dv" in df.columns and "ten_dv" in df.columns:
            mask_ten = df["ten_dv"].astype(str).str.strip().str.lower() == pgd_user.strip().lower()
            if not mask_ten.any():
                mask_ma = df["ma_dv"].astype(str).str.strip().str.lower() == pgd_user.strip().lower()
                return df[mask_ma]
            return df[mask_ten]
        elif "ten_dv" in df.columns:
            return df[df["ten_dv"].astype(str).str.strip().str.lower() == pgd_user.strip().lower()]
        elif "ma_dv" in df.columns:
            return df[df["ma_dv"].astype(str).str.strip().str.lower() == pgd_user.strip().lower()]
    return df  # mode "cn" → trả về toàn bộ


def cdtotkvv_ten_sheet_excel(ten_hien_thi: str, da_dung: set[str]) -> str:
    """Tên sheet Excel ≤31 ký tự, không ký tự cấm, không trùng."""
    forbidden = set("[]:*?/\\")
    base = "".join("_" if c in forbidden else c for c in ten_hien_thi).strip() or "Tieu_chi"
    base = base[:28]
    ten = base[:31]
    n = 1
    while ten in da_dung:
        hau_to = f"_{n}"
        ten = (base[: 31 - len(hau_to)]).rstrip("_") + hau_to
        n += 1
    da_dung.add(ten)
    return ten


def fmt_xuat_to_khong_dat_vn(df: pd.DataFrame) -> pd.DataFrame:
    """Bản sao DataFrame đã format số/tiền chuẩn VN cho Excel/PDF (không dùng cho thống kê .mean())."""
    out = df.copy()
    if "Dư nợ" in out.columns:
        out["Dư nợ"] = pd.to_numeric(out["Dư nợ"], errors="coerce").map(
            lambda v: fmt_so(v) if pd.notna(v) else "—"
        )
    if "Số dư TK" in out.columns:
        out["Số dư TK"] = pd.to_numeric(out["Số dư TK"], errors="coerce").map(
            lambda v: fmt_so(v) if pd.notna(v) else "—"
        )
    for cot in ("Điểm đạt được", "Điểm tối đa", "Thiếu", "Tổng điểm"):
        if cot not in out.columns:
            continue
        out[cot] = out[cot].apply(
            lambda v: fmt_so(int(round(float(v)))) if pd.notna(v) and v != "" else "—"
        )
    return out
