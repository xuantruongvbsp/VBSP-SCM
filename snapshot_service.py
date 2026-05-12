"""
snapshot_service.py — Lưu và đọc HSTD Snapshot theo tháng.

API chính:
    luu_snapshot(df_full, username)   → KetQuaUpload
    doc_snapshot(ky)                  → pd.DataFrame   (tổng hợp theo PGD)
    doc_snapshot_range(tu_ky, den_ky) → pd.DataFrame   (nhiều kỳ, dùng cho line chart)
    danh_sach_ky()                    → list[str]       (các kỳ đã có, mới→cũ)
    xoa_snapshot(ky, username)        → None
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import pandas as pd

import db
from config import (
    COT_DU_NO_QH,
    COT_DU_NO_TH,
    COT_MA_CHUONG_TRINH,
    COT_MA_KH,
    COT_NGAY_SL,
    COT_NGUON_VON,
    COT_SO_KU,
    COT_TEN_PGD,
    COT_TONG_DU_NO,
    DON_VI_CHI_NHANH,
)
from services.upload_service import KetQuaUpload

_COT_DNK = "Dư nợ khoanh"
_COT_GN_NAM_ALIASES = ("Giải ngân trong năm", "Giải ngân Năm", "Giải ngân năm")


def _ky_tu_df(df: pd.DataFrame) -> str:
    """Suy ra kỳ "YYYY-MM" từ cột Ngày số liệu. Fallback: tháng hiện tại."""
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


def _gn_nam_col(df: pd.DataFrame) -> Optional[str]:
    """Tìm cột giải ngân trong năm theo aliases."""
    for alias in _COT_GN_NAM_ALIASES:
        if alias in df.columns:
            return alias
    return None


def luu_snapshot(df_full: pd.DataFrame, username: str) -> KetQuaUpload:
    """
    Tính tổng hợp từ df_full (HSTD toàn CN đã merge) và lưu vào bảng hstd_snapshot.

    - Tổng hợp theo: (ky, ten_pgd, ma_ct, nguon_von)
    - Thêm dòng tổng toàn CN: ten_pgd = "__CN__", ma_ct = "ALL", nguon_von = "ALL"
    - Dùng INSERT OR REPLACE để upsert an toàn (chạy lại cùng kỳ → ghi đè)
    """
    if df_full is None or df_full.empty:
        return KetQuaUpload(False, "Không có dữ liệu HSTD để tạo snapshot.")

    ky = _ky_tu_df(df_full)
    ngay_sl_val = None
    if COT_NGAY_SL in df_full.columns:
        sl = df_full[COT_NGAY_SL].dropna()
        if len(sl):
            ngay_sl_val = str(sl.iloc[0])

    df = df_full.copy()
    for col in (COT_TONG_DU_NO, COT_DU_NO_TH, COT_DU_NO_QH, _COT_DNK):
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    gn_col = _gn_nam_col(df)
    if gn_col is None:
        df["__gn_nam__"] = 0.0
        gn_col = "__gn_nam__"
    else:
        df[gn_col] = pd.to_numeric(df[gn_col], errors="coerce").fillna(0.0)

    if COT_TEN_PGD not in df.columns:
        df[COT_TEN_PGD] = DON_VI_CHI_NHANH
    if COT_MA_CHUONG_TRINH not in df.columns:
        df[COT_MA_CHUONG_TRINH] = "0"
    if COT_NGUON_VON not in df.columns:
        df[COT_NGUON_VON] = "ALL"

    df[COT_MA_CHUONG_TRINH] = df[COT_MA_CHUONG_TRINH].astype(str).str.strip()
    df[COT_NGUON_VON] = df[COT_NGUON_VON].astype(str).str.strip().str.upper()

    grp = df.groupby([COT_TEN_PGD, COT_MA_CHUONG_TRINH, COT_NGUON_VON], dropna=False)
    agg = (
        grp.agg(
            tong_du_no=(COT_TONG_DU_NO, "sum"),
            du_no_th=(COT_DU_NO_TH, "sum"),
            du_no_qh=(COT_DU_NO_QH, "sum"),
            du_no_khoanh=(_COT_DNK, "sum"),
            so_ho=(COT_MA_KH, "nunique"),
            so_ku=(COT_SO_KU, "nunique"),
            gn_nam=(gn_col, "sum"),
        )
        .reset_index()
    )

    tong_cn = pd.DataFrame(
        [
            {
                COT_TEN_PGD: "__CN__",
                COT_MA_CHUONG_TRINH: "ALL",
                COT_NGUON_VON: "ALL",
                "tong_du_no": float(df[COT_TONG_DU_NO].sum()),
                "du_no_th": float(df[COT_DU_NO_TH].sum()),
                "du_no_qh": float(df[COT_DU_NO_QH].sum()),
                "du_no_khoanh": float(df[_COT_DNK].sum()),
                "so_ho": int(df[COT_MA_KH].nunique()),
                "so_ku": int(df[COT_SO_KU].nunique()),
                "gn_nam": float(df[gn_col].sum()),
            }
        ]
    )

    grp_pgd = df.groupby(COT_TEN_PGD, dropna=False)
    agg_pgd = (
        grp_pgd.agg(
            tong_du_no=(COT_TONG_DU_NO, "sum"),
            du_no_th=(COT_DU_NO_TH, "sum"),
            du_no_qh=(COT_DU_NO_QH, "sum"),
            du_no_khoanh=(_COT_DNK, "sum"),
            so_ho=(COT_MA_KH, "nunique"),
            so_ku=(COT_SO_KU, "nunique"),
            gn_nam=(gn_col, "sum"),
        )
        .reset_index()
    )
    agg_pgd[COT_MA_CHUONG_TRINH] = "ALL"
    agg_pgd[COT_NGUON_VON] = "ALL"

    rows_to_insert = pd.concat([agg, agg_pgd, tong_cn], ignore_index=True)

    so_dong = 0
    try:
        with db.get_conn() as conn:
            for _, row in rows_to_insert.iterrows():
                conn.execute(
                    """INSERT OR REPLACE INTO hstd_snapshot
                       (ky, ten_pgd, ma_ct, nguon_von,
                        tong_du_no, du_no_th, du_no_qh, du_no_khoanh,
                        so_ho, so_ku, gn_nam, ngay_so_lieu, created_by)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        ky,
                        str(row[COT_TEN_PGD]),
                        str(row[COT_MA_CHUONG_TRINH]),
                        str(row[COT_NGUON_VON]),
                        float(row["tong_du_no"]),
                        float(row["du_no_th"]),
                        float(row["du_no_qh"]),
                        float(row["du_no_khoanh"]),
                        int(row["so_ho"]),
                        int(row["so_ku"]),
                        float(row["gn_nam"]),
                        ngay_sl_val,
                        username,
                    ),
                )
                so_dong += 1
            conn.commit()
        db.ghi_audit(username, "luu_snapshot", f"Kỳ {ky} — {so_dong} dòng tổng hợp")
        return KetQuaUpload(True, f"✅ Đã lưu snapshot kỳ **{ky}** — {so_dong} dòng tổng hợp")
    except Exception as e:
        db.ghi_audit(username, "luu_snapshot_loi", str(e))
        return KetQuaUpload(False, f"❌ Lỗi lưu snapshot: {e}")


def doc_snapshot(ky: str) -> pd.DataFrame:
    """Đọc snapshot của 1 kỳ, chỉ lấy dòng tổng theo PGD (ma_ct='ALL')."""
    try:
        with db.get_conn() as conn:
            rows = conn.execute(
                """SELECT ten_pgd, tong_du_no, du_no_th, du_no_qh, du_no_khoanh,
                          so_ho, so_ku, gn_nam, ngay_so_lieu
                   FROM hstd_snapshot
                   WHERE ky = ? AND ma_ct = 'ALL' AND nguon_von = 'ALL'
                   ORDER BY ten_pgd""",
                (ky,),
            ).fetchall()
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([dict(r) for r in rows])
    except Exception:
        return pd.DataFrame()


def doc_snapshot_range(tu_ky: str, den_ky: str) -> pd.DataFrame:
    """
    Đọc nhiều kỳ liên tiếp, dòng tổng toàn CN (ten_pgd='__CN__').
    Dùng cho line chart tăng trưởng theo tháng.
    """
    try:
        with db.get_conn() as conn:
            rows = conn.execute(
                """SELECT ky, tong_du_no, du_no_qh, du_no_khoanh, so_ho, gn_nam
                   FROM hstd_snapshot
                   WHERE ten_pgd = '__CN__' AND ma_ct = 'ALL' AND nguon_von = 'ALL'
                     AND ky BETWEEN ? AND ?
                   ORDER BY ky""",
                (tu_ky, den_ky),
            ).fetchall()
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([dict(r) for r in rows])
    except Exception:
        return pd.DataFrame()


def danh_sach_ky() -> list[str]:
    """Trả về list kỳ đã có snapshot, mới → cũ."""
    try:
        with db.get_conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT ky FROM hstd_snapshot ORDER BY ky DESC"
            ).fetchall()
        return [r["ky"] for r in rows]
    except Exception:
        return []


def xoa_snapshot(ky: str, username: str) -> None:
    """Xóa toàn bộ snapshot của 1 kỳ."""
    try:
        with db.get_conn() as conn:
            conn.execute("DELETE FROM hstd_snapshot WHERE ky = ?", (ky,))
            conn.commit()
        db.ghi_audit(username, "xoa_snapshot", f"Đã xóa snapshot kỳ {ky}")
    except Exception as e:
        db.ghi_audit(username, "xoa_snapshot_loi", str(e))

