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
    logger.error("Lỗi trong khối except: %s", e, exc_info=True)
    import logging
    logger = logging.getLogger(__name__)
try:
    from upload_service import KetQuaUpload
except Exception:
    logger.error("Lỗi trong khối except: %s", e, exc_info=True)
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
                logger.error("Lỗi trong khối except: %s", e, exc_info=True)
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
    except Exception as e:
        logger.error("doc_snapshot: lỗi đọc snapshot kỳ %s — %s", ky, e, exc_info=True)
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
    except Exception as e:
        logger.error("doc_snapshot_range: lỗi đọc snapshot từ %s đến %s — %s", tu_ky, den_ky, e, exc_info=True)
        return pd.DataFrame()


def danh_sach_ky() -> list[str]:
    """Danh sách kỳ đã có snapshot, mới → cũ."""
    try:
        with db.get_conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT ky FROM hstd_snapshot ORDER BY ky DESC"
            ).fetchall()
        return [r["ky"] for r in rows]
    except Exception as e:
        logger.error("danh_sach_ky: lỗi đọc danh sách kỳ snapshot — %s", e, exc_info=True)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# NQ11 SNAPSHOT
# ─────────────────────────────────────────────────────────────────────────────

def _ky_tu_nq11(df: pd.DataFrame) -> str:
    """Suy ra kỳ 'YYYY-MM' từ cột Ngày báo cáo của NQ11."""
    try:
        from config import COT_NQ11_NGAY_BC
        if COT_NQ11_NGAY_BC in df.columns:
            sl = df[COT_NQ11_NGAY_BC].dropna()
            if len(sl):
                val = str(sl.iloc[0])
                if "/" in val:
                    parts = val.split("/")
                    if len(parts) == 3:
                        return f"{parts[2][:4]}-{parts[1].zfill(2)}"
                dt = pd.to_datetime(val, errors="coerce")
                if pd.notna(dt):
                    return dt.strftime("%Y-%m")
    except Exception:
        logger.error("Lỗi trong khối except: %s", e, exc_info=True)
        pass
    return datetime.now().strftime("%Y-%m")


def luu_nq11_snapshot(df_nq11: pd.DataFrame, username: str) -> KetQuaUpload:
    """Tổng hợp df_nq11 (NQ11 toàn CN) → lưu vào nq11_snapshot.
    INSERT OR REPLACE — chạy lại cùng kỳ sẽ ghi đè.
    Lưu 2 loại: tổng theo PGD + tổng CN ('__CN__').
    """
    if df_nq11 is None or df_nq11.empty:
        return KetQuaUpload(False, "Không có dữ liệu NQ11 để tạo snapshot.")

    from config import (
        COT_TEN_PGD, COT_DNO_NQ11, COT_NQ11_NO_TH, COT_NQ11_NO_QH,
        COT_NQ11_MA_KH, COT_NQ11_SO_TIEN_GN, COT_NQ11_NGAY_BC,
        DON_VI_CHI_NHANH,
    )

    ky = _ky_tu_nq11(df_nq11)

    # Lấy ngày báo cáo
    ngay_bc = None
    if COT_NQ11_NGAY_BC in df_nq11.columns:
        sl = df_nq11[COT_NQ11_NGAY_BC].dropna()
        if len(sl):
            ngay_bc = str(sl.iloc[0])

    df = df_nq11.copy()

    # Ép kiểu cột số
    for col in (COT_DNO_NQ11, COT_NQ11_NO_TH, COT_NQ11_NO_QH, COT_NQ11_SO_TIEN_GN):
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    if COT_TEN_PGD not in df.columns:
        df[COT_TEN_PGD] = DON_VI_CHI_NHANH
    if COT_NQ11_MA_KH not in df.columns:
        df[COT_NQ11_MA_KH] = ""

    gn_col = COT_NQ11_SO_TIEN_GN if COT_NQ11_SO_TIEN_GN in df.columns else None

    def _agg_nq11(grp_df, pgd_val):
        return (
            pgd_val,
            float(grp_df[COT_DNO_NQ11].sum()),
            float(grp_df[COT_NQ11_NO_TH].sum()),
            float(grp_df[COT_NQ11_NO_QH].sum()),
            int(grp_df[COT_NQ11_MA_KH].nunique()),
            float(grp_df[gn_col].sum()) if gn_col else 0.0,
        )

    rows = []
    for pgd, g in df.groupby(COT_TEN_PGD, dropna=False):
        rows.append(_agg_nq11(g, str(pgd)))
    rows.append(_agg_nq11(df, "__CN__"))

    so_dong = 0
    try:
        with db.get_conn() as conn:
            for (pgd, tdn, nth, nqh, so_kh, gn) in rows:
                conn.execute(
                    """INSERT OR REPLACE INTO nq11_snapshot
                       (ky, ten_pgd, tong_du_no, no_th, no_qh, so_kh, gn_nam, ngay_bc, created_by)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (ky, pgd, tdn, nth, nqh, so_kh, gn, ngay_bc, username),
                )
                so_dong += 1
            conn.commit()
        logger.info("luu_nq11_snapshot: kỳ=%s, %d dòng", ky, so_dong)
        db.ghi_audit(username, "luu_nq11_snapshot", f"Kỳ {ky} — {so_dong} dòng")
        return KetQuaUpload(True, f"✅ Đã lưu NQ11 snapshot kỳ **{ky}** ({so_dong} dòng)")
    except Exception as e:
        logger.error("luu_nq11_snapshot: thất bại kỳ=%s — %s", ky, e, exc_info=True)
        return KetQuaUpload(False, f"❌ Lỗi lưu NQ11 snapshot: {e}")


def doc_nq11_snapshot(ky: str) -> pd.DataFrame:
    """Tổng theo PGD của 1 kỳ NQ11."""
    try:
        with db.get_conn() as conn:
            rows = conn.execute(
                """SELECT ten_pgd, tong_du_no, no_th, no_qh, so_kh, gn_nam, ngay_bc
                   FROM nq11_snapshot
                   WHERE ky=?
                   ORDER BY ten_pgd""",
                (ky,)
            ).fetchall()
        return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()
    except Exception as e:
        logger.error("doc_nq11_snapshot: lỗi kỳ %s — %s", ky, e, exc_info=True)
        return pd.DataFrame()


def danh_sach_ky_nq11() -> list[str]:
    """Danh sách kỳ đã có NQ11 snapshot, mới → cũ."""
    try:
        with db.get_conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT ky FROM nq11_snapshot ORDER BY ky DESC"
            ).fetchall()
        return [r["ky"] for r in rows]
    except Exception as e:
        logger.error("danh_sach_ky_nq11: %s", e, exc_info=True)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# GQVL SNAPSHOT
# ─────────────────────────────────────────────────────────────────────────────

def luu_gqvl_snapshot(df_gqvl: pd.DataFrame, username: str) -> KetQuaUpload:
    """Tổng hợp df_gqvl (GQVL toàn CN, sau khi đã rename cột) → lưu vào gqvl_snapshot.
    INSERT OR REPLACE — chạy lại cùng kỳ sẽ ghi đè.
    Lưu 2 loại: tổng theo PGD + tổng CN ('__CN__').
    """
    if df_gqvl is None or df_gqvl.empty:
        return KetQuaUpload(False, "Không có dữ liệu GQVL để tạo snapshot.")

    from config import COT_TEN_PGD, DON_VI_CHI_NHANH

    _COL_TH    = "Dư nợ trong hạn"
    _COL_QH    = "Dư nợ quá hạn"
    _COL_KH    = "Dư nợ khoanh"
    _COL_MA_KH = "Mã KH"
    _COL_GN    = "Giải ngân trong năm"

    ky = datetime.now().strftime("%Y-%m")

    df = df_gqvl.copy()

    for col in (_COL_TH, _COL_QH, _COL_KH, _COL_GN):
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    if COT_TEN_PGD not in df.columns:
        df[COT_TEN_PGD] = DON_VI_CHI_NHANH
    if _COL_MA_KH not in df.columns:
        df[_COL_MA_KH] = ""

    def _agg_gqvl(grp_df, pgd_val):
        return (
            pgd_val,
            float(grp_df[_COL_TH].sum()),
            float(grp_df[_COL_QH].sum()),
            float(grp_df[_COL_KH].sum()),
            int(grp_df[_COL_MA_KH].nunique()),
            float(grp_df[_COL_GN].sum()),
        )

    rows = []
    for pgd, g in df.groupby(COT_TEN_PGD, dropna=False):
        rows.append(_agg_gqvl(g, str(pgd)))
    rows.append(_agg_gqvl(df, "__CN__"))

    so_dong = 0
    try:
        with db.get_conn() as conn:
            for (pgd, dth, dqh, dkh, so_kh, gn) in rows:
                conn.execute(
                    """INSERT OR REPLACE INTO gqvl_snapshot
                       (ky, ten_pgd, dn_th, dn_qh, dn_khoanh, so_kh, gn_nam, created_by)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (ky, pgd, dth, dqh, dkh, so_kh, gn, username),
                )
                so_dong += 1
            conn.commit()
        logger.info("luu_gqvl_snapshot: kỳ=%s, %d dòng", ky, so_dong)
        db.ghi_audit(username, "luu_gqvl_snapshot", f"Kỳ {ky} — {so_dong} dòng")
        return KetQuaUpload(True, f"✅ Đã lưu GQVL snapshot kỳ **{ky}** ({so_dong} dòng)")
    except Exception as e:
        logger.error("luu_gqvl_snapshot: thất bại kỳ=%s — %s", ky, e, exc_info=True)
        return KetQuaUpload(False, f"❌ Lỗi lưu GQVL snapshot: {e}")


def doc_gqvl_snapshot(ky: str) -> pd.DataFrame:
    """Tổng theo PGD của 1 kỳ GQVL."""
    try:
        with db.get_conn() as conn:
            rows = conn.execute(
                """SELECT ten_pgd, dn_th, dn_qh, dn_khoanh, so_kh, gn_nam
                   FROM gqvl_snapshot
                   WHERE ky=?
                   ORDER BY ten_pgd""",
                (ky,)
            ).fetchall()
        return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()
    except Exception as e:
        logger.error("doc_gqvl_snapshot: lỗi kỳ %s — %s", ky, e, exc_info=True)
        return pd.DataFrame()


def danh_sach_ky_gqvl() -> list[str]:
    """Danh sách kỳ đã có GQVL snapshot, mới → cũ."""
    try:
        with db.get_conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT ky FROM gqvl_snapshot ORDER BY ky DESC"
            ).fetchall()
        return [r["ky"] for r in rows]
    except Exception as e:
        logger.error("danh_sach_ky_gqvl: %s", e, exc_info=True)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# CDTOTKVV SNAPSHOT
# ─────────────────────────────────────────────────────────────────────────────

def luu_cdtotkvv_snapshot(df_cdtotkvv: pd.DataFrame, ky: str, username: str) -> KetQuaUpload:
    """Tổng hợp df_cdtotkvv (CDTOTKVV toàn CN) → lưu vào cdtotkvv_snapshot.
    ky: 'YYYY-MM' — thường lấy cùng kỳ với HSTD snapshot.
    INSERT OR REPLACE — chạy lại cùng kỳ sẽ ghi đè.
    Lưu 2 loại: tổng theo PGD + tổng CN ('__CN__').
    """
    if df_cdtotkvv is None or df_cdtotkvv.empty:
        return KetQuaUpload(False, "Không có dữ liệu CDTOTKVV để tạo snapshot.")

    # Inline aggregation — không dùng tong_hop_theo_pgd() (có @st.cache_data)
    # vì hàm này có thể được gọi từ background thread
    _XEP_TOT = "Tốt"
    _XEP_KHA = "Khá"
    _XEP_TB  = "Trung bình"
    _XEP_YEU = "Yếu"

    df_src = df_cdtotkvv.copy()
    # Chuẩn hóa cột bắt buộc
    if "tong_diem" not in df_src.columns:
        df_src["tong_diem"] = 0.0
    df_src["tong_diem"] = pd.to_numeric(df_src["tong_diem"], errors="coerce").fillna(0.0)
    if "stt" not in df_src.columns:
        df_src["stt"] = range(len(df_src))
    if "ten_dv" not in df_src.columns:
        df_src["ten_dv"] = df_src["ma_dv"] if "ma_dv" in df_src.columns else "?"
    if "ma_dv" not in df_src.columns:
        df_src["ma_dv"] = "?"

    grp_key = ["ma_dv", "ten_dv"]
    nhom = df_src.groupby(grp_key, as_index=False)
    df_pgd = nhom.agg(tong_to=("stt", "count"), tong_diem_tb=("tong_diem", "mean"))
    for col_name, xep_val in [("to_tot", _XEP_TOT), ("to_kha", _XEP_KHA),
                               ("to_tb", _XEP_TB), ("to_yeu", _XEP_YEU)]:
        if "xep_loai" in df_src.columns:
            sub = df_src[df_src["xep_loai"] == xep_val]
        else:
            sub = df_src.iloc[:0]
        if not sub.empty:
            sub_cnt = sub.groupby(grp_key, as_index=False).agg(**{col_name: ("stt", "count")})
            df_pgd = df_pgd.merge(sub_cnt, on=grp_key, how="left")
        if col_name not in df_pgd.columns:
            df_pgd[col_name] = 0
        df_pgd[col_name] = df_pgd[col_name].fillna(0).astype(int)

    if df_pgd is None or df_pgd.empty:
        return KetQuaUpload(False, "Không tổng hợp được CDTOTKVV theo PGD.")

    rows = []
    for _, row in df_pgd.iterrows():
        pgd_name = str(row.get("ten_dv", "")).strip() or str(row.get("ma_dv", ""))
        rows.append((
            pgd_name,
            int(row.get("tong_to", 0)),
            int(row.get("to_tot", 0)),
            int(row.get("to_kha", 0)),
            int(row.get("to_tb", 0)),
            int(row.get("to_yeu", 0)),
            float(row.get("tong_diem_tb", 0.0)),
        ))

    # Thêm hàng tổng CN
    rows.append((
        "__CN__",
        int(df_pgd["tong_to"].sum()),
        int(df_pgd["to_tot"].sum()),
        int(df_pgd["to_kha"].sum()),
        int(df_pgd["to_tb"].sum()),
        int(df_pgd["to_yeu"].sum()),
        float(df_src["tong_diem"].mean()) if "tong_diem" in df_src.columns else 0.0,
    ))

    so_dong = 0
    try:
        with db.get_conn() as conn:
            for (pgd, so_to, so_tot, so_kha, so_tb, so_yeu, diem_tb) in rows:
                conn.execute(
                    """INSERT OR REPLACE INTO cdtotkvv_snapshot
                       (ky, ten_pgd, so_to, so_tot, so_kha, so_tb, so_yeu, diem_tb, created_by)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (ky, pgd, so_to, so_tot, so_kha, so_tb, so_yeu, diem_tb, username),
                )
                so_dong += 1
            conn.commit()
        logger.info("luu_cdtotkvv_snapshot: kỳ=%s, %d dòng", ky, so_dong)
        db.ghi_audit(username, "luu_cdtotkvv_snapshot", f"Kỳ {ky} — {so_dong} dòng")
        return KetQuaUpload(True, f"✅ Đã lưu CDTOTKVV snapshot kỳ **{ky}** ({so_dong} dòng)")
    except Exception as e:
        logger.error("luu_cdtotkvv_snapshot: thất bại kỳ=%s — %s", ky, e, exc_info=True)
        return KetQuaUpload(False, f"❌ Lỗi lưu CDTOTKVV snapshot: {e}")


def doc_cdtotkvv_snapshot(ky: str) -> pd.DataFrame:
    """Tổng theo PGD của 1 kỳ CDTOTKVV."""
    try:
        with db.get_conn() as conn:
            rows = conn.execute(
                """SELECT ten_pgd, so_to, so_tot, so_kha, so_tb, so_yeu, diem_tb
                   FROM cdtotkvv_snapshot
                   WHERE ky=?
                   ORDER BY ten_pgd""",
                (ky,)
            ).fetchall()
        return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()
    except Exception as e:
        logger.error("doc_cdtotkvv_snapshot: lỗi kỳ %s — %s", ky, e, exc_info=True)
        return pd.DataFrame()


def danh_sach_ky_cdtotkvv() -> list[str]:
    """Danh sách kỳ đã có CDTOTKVV snapshot, mới → cũ."""
    try:
        with db.get_conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT ky FROM cdtotkvv_snapshot ORDER BY ky DESC"
            ).fetchall()
        return [r["ky"] for r in rows]
    except Exception as e:
        logger.error("danh_sach_ky_cdtotkvv: %s", e, exc_info=True)
        return []


def xoa_snapshot(ky: str, username: str) -> None:
    try:
        with db.get_conn() as conn:
            conn.execute("DELETE FROM hstd_snapshot WHERE ky=?", (ky,))
            conn.commit()
        db.ghi_audit(username, "xoa_snapshot", f"Đã xóa snapshot kỳ {ky}")
    except Exception as e:
        logger.error("xoa_snapshot: lỗi xóa snapshot kỳ %s — %s", ky, e, exc_info=True)
        db.ghi_audit(username, "xoa_snapshot_loi", str(e))
