"""
snapshot_service.py — Lưu và đọc HSTD Snapshot theo tháng vào SQLite.

API:
    luu_snapshot(df_full, username)        → KetQuaUpload
    doc_snapshot(ky)                       → pd.DataFrame  (tổng theo PGD, ma_ct='ALL')
    doc_snapshot_range(tu_ky, den_ky)      → pd.DataFrame  (nhiều kỳ, ten_pgd='__CN__')
    danh_sach_ky()                         → list[str]      (mới → cũ)
    xoa_snapshot(ky, username)             → None
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd

import db
try:
    from logger import get_logger
    logger = get_logger(__name__)
except Exception:
    import logging
    logger = logging.getLogger(__name__)
try:
    from upload_service import KetQuaUpload
except Exception:
    from services.upload_service import KetQuaUpload
from config import (
    COT_MA_CHUONG_TRINH,
    COT_MA_KH,
    COT_NGAY_SL,
    COT_NGUON_VON,
    COT_SO_KU,
    COT_TEN_PGD,
    COT_TONG_DU_NO,
    COT_DU_NO_TH,
    COT_DU_NO_QH,
    DON_VI_CHI_NHANH,
)

_COT_DNK = "Dư nợ khoanh"
_GN_NAM_ALIASES = ("Giải ngân trong năm", "Giải ngân Năm", "Giải ngân năm")


def _ky_tu_df(df: pd.DataFrame) -> str:
    """Suy ra kỳ 'YYYY-MM' từ cột Ngày số liệu. Fallback: tháng hiện tại."""
    if COT_NGAY_SL in df.columns:
        sl = df[COT_NGAY_SL].dropna()
        if len(sl):
            try:
                val = str(sl.iloc[0])
                if "/" in val:
                    parts = val.split("/")
                    return f"{parts[2][:4]}-{parts[1].zfill(2)}"
                dt = pd.to_datetime(val, errors="coerce")
                if pd.notna(dt):
                    return dt.strftime("%Y-%m")
            except Exception:
                pass
    return datetime.now().strftime("%Y-%m")


def _gn_col(df: pd.DataFrame):
    for alias in _GN_NAM_ALIASES:
        if alias in df.columns:
            return alias
    return None


def luu_snapshot(df_full: pd.DataFrame, username: str) -> KetQuaUpload:
    """
    Tổng hợp df_full (HSTD toàn CN) → lưu vào hstd_snapshot.
    INSERT OR REPLACE → chạy lại cùng kỳ sẽ ghi đè, không trùng.
    Lưu 3 loại dòng:
      - Chi tiết: (ten_pgd, ma_ct, nguon_von)
      - Tổng PGD: (ten_pgd, 'ALL', 'ALL')
      - Tổng CN:  ('__CN__', 'ALL', 'ALL')
    """
    if df_full is None or df_full.empty:
        return KetQuaUpload(False, "Không có dữ liệu HSTD để tạo snapshot.")

    ky = _ky_tu_df(df_full)
    ngay_sl = (
        str(df_full[COT_NGAY_SL].dropna().iloc[0])
        if COT_NGAY_SL in df_full.columns and len(df_full[COT_NGAY_SL].dropna())
        else None
    )

    df = df_full.copy()
    for col in (COT_TONG_DU_NO, COT_DU_NO_TH, COT_DU_NO_QH, _COT_DNK):
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    gn = _gn_col(df)
    if gn is None:
        df["__gn__"] = 0.0
        gn = "__gn__"
    else:
        df[gn] = pd.to_numeric(df[gn], errors="coerce").fillna(0.0)

    if COT_TEN_PGD not in df.columns:
        df[COT_TEN_PGD] = DON_VI_CHI_NHANH
    if COT_MA_CHUONG_TRINH not in df.columns:
        df[COT_MA_CHUONG_TRINH] = "0"
    if COT_NGUON_VON not in df.columns:
        df[COT_NGUON_VON] = "ALL"

    df[COT_MA_CHUONG_TRINH] = df[COT_MA_CHUONG_TRINH].astype(str).str.strip()
    df[COT_NGUON_VON] = df[COT_NGUON_VON].astype(str).str.strip().str.upper()

    def _agg(grp_df, pgd_val, ct_val, nv_val):
        return (
            pgd_val,
            ct_val,
            nv_val,
            float(grp_df[COT_TONG_DU_NO].sum()),
            float(grp_df[COT_DU_NO_TH].sum()),
            float(grp_df[COT_DU_NO_QH].sum()),
            float(grp_df[_COT_DNK].sum()),
            int(grp_df[COT_MA_KH].nunique()),
            int(grp_df[COT_SO_KU].nunique()),
            float(grp_df[gn].sum()),
        )

    rows = []
    for (pgd, ct, nv), g in df.groupby([COT_TEN_PGD, COT_MA_CHUONG_TRINH, COT_NGUON_VON], dropna=False):
        rows.append(_agg(g, str(pgd), str(ct), str(nv)))
    for pgd, g in df.groupby(COT_TEN_PGD, dropna=False):
        rows.append(_agg(g, str(pgd), "ALL", "ALL"))
    rows.append(_agg(df, "__CN__", "ALL", "ALL"))

    so_dong = 0
    logger.info("luu_snapshot: bắt đầu kỳ=%s, %d dòng tổng hợp", ky, len(rows))
    try:
        with db.get_conn() as conn:
            for (pgd, ct, nv, tdn, dth, dqh, dnk, so_ho, so_ku, gn_nam) in rows:
                conn.execute(
                    """INSERT OR REPLACE INTO hstd_snapshot
                       (ky, ten_pgd, ma_ct, nguon_von,
                        tong_du_no, du_no_th, du_no_qh, du_no_khoanh,
                        so_ho, so_ku, gn_nam, ngay_so_lieu, created_by)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        ky,
                        pgd,
                        ct,
                        nv,
                        tdn,
                        dth,
                        dqh,
                        dnk,
                        so_ho,
                        so_ku,
                        gn_nam,
                        ngay_sl,
                        username
                    ),
                )
                so_dong += 1
            conn.commit()
        logger.info("luu_snapshot: hoàn thành kỳ=%s, đã ghi %d dòng", ky, so_dong)
        db.ghi_audit(username, "luu_snapshot", f"Kỳ {ky} — {so_dong} dòng")
        return KetQuaUpload(True, f"✅ Đã lưu snapshot kỳ **{ky}** ({so_dong} dòng tổng hợp)")
    except Exception as e:
        logger.error("luu_snapshot: thất bại kỳ=%s — %s", ky, e, exc_info=True)
        db.ghi_audit(username, "luu_snapshot_loi", str(e))
        return KetQuaUpload(False, f"❌ Lỗi lưu snapshot: {e}")


def doc_snapshot(ky: str) -> pd.DataFrame:
    """Tổng theo PGD của 1 kỳ (ma_ct='ALL', nguon_von='ALL')."""
    try:
        with db.get_conn() as conn:
            rows = conn.execute(
                """SELECT ten_pgd, tong_du_no, du_no_th, du_no_qh, du_no_khoanh,
                          so_ho, so_ku, gn_nam, ngay_so_lieu
                   FROM hstd_snapshot
                   WHERE ky=? AND ma_ct='ALL' AND nguon_von='ALL'
                   ORDER BY ten_pgd""",
                (ky,)
            ).fetchall()
        return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def doc_snapshot_range(tu_ky: str, den_ky: str) -> pd.DataFrame:
    """Tổng toàn CN qua nhiều kỳ — dùng cho line chart."""
    try:
        with db.get_conn() as conn:
            rows = conn.execute(
                """SELECT ky, tong_du_no, du_no_qh, du_no_khoanh, so_ho, gn_nam
                   FROM hstd_snapshot
                   WHERE ten_pgd='__CN__' AND ma_ct='ALL' AND nguon_von='ALL'
                     AND ky BETWEEN ? AND ?
                   ORDER BY ky""",
                (tu_ky, den_ky),
            ).fetchall()
        return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def danh_sach_ky() -> list[str]:
    """Danh sách kỳ đã có snapshot, mới → cũ."""
    try:
        with db.get_conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT ky FROM hstd_snapshot ORDER BY ky DESC"
            ).fetchall()
        return [r["ky"] for r in rows]
    except Exception:
        return []


def xoa_snapshot(ky: str, username: str) -> None:
    try:
        with db.get_conn() as conn:
            conn.execute("DELETE FROM hstd_snapshot WHERE ky=?", (ky,))
            conn.commit()
        db.ghi_audit(username, "xoa_snapshot", f"Đã xóa snapshot kỳ {ky}")
    except Exception as e:
        db.ghi_audit(username, "xoa_snapshot_loi", str(e))
