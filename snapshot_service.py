"""
snapshot_service.py — Lưu và đọc HSTD Snapshot theo tháng vào SQLite.

API:
    luu_snapshot(df_full, username)           → KetQuaUpload
    doc_snapshot(ky)                          → pd.DataFrame  (tổng theo PGD, ma_ct='ALL')
    doc_snapshot_range(tu_ky, den_ky)         → pd.DataFrame  (nhiều kỳ, ten_pgd='__CN__')
    doc_snapshot_theo_ct(ky)                  → pd.DataFrame  (chi tiết theo ma_ct, ten_pgd='__CN__')
    doc_snapshot_multi(ky_list: tuple)        → pd.DataFrame  (tổng CN cho danh sách kỳ tùy chọn)
    danh_sach_ky()                            → list[str]      (mới → cũ)
    xoa_snapshot(ky, username)               → None
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

import db
try:
    from logger import get_logger
    logger = get_logger(__name__)
except Exception:
    import logging
    logger = logging.getLogger(__name__)
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
    COT_GIAI_NGAN_TRONG_NAM,
    DON_VI_CHI_NHANH,
    COT_DVUT,
    COT_LAI_TON,
    COT_LAI_TON_QH,
    COT_SO_DU_TG,
    COT_TEN_TO,
    COT_TEN_XA,
    DS_PGD,
)

_COT_DNK = "Dư nợ khoanh"
_GN_NAM_ALIASES = (COT_GIAI_NGAN_TRONG_NAM, "Giải ngân Năm", "Giải ngân năm")


def _suy_ra_ky(df: pd.DataFrame, col_ngay: str) -> str:
    """Suy ra kỳ YYYY-MM từ ngày lớn nhất của một cột; fallback tháng hiện tại."""
    if df is not None and col_ngay in df.columns:
        sl = df[col_ngay].dropna()
        if len(sl):
            try:
                dt = pd.to_datetime(sl, errors="coerce", dayfirst=True, format="mixed").dropna()
                if not dt.empty:
                    return dt.max().strftime("%Y-%m")
            except Exception as e:
                logger.error("_suy_ra_ky: lỗi parse cột %s — %s", col_ngay, e, exc_info=True)
    return datetime.now().strftime("%Y-%m")


def _ky_tu_df(df: pd.DataFrame) -> str:
    """Suy ra kỳ từ ngày số liệu lớn nhất; fallback tháng hiện tại."""
    return _suy_ra_ky(df, COT_NGAY_SL)


def _ngay_so_lieu_max(df: pd.DataFrame) -> str | None:
    if COT_NGAY_SL not in df.columns:
        return None
    try:
        dt = pd.to_datetime(
            df[COT_NGAY_SL], errors="coerce", dayfirst=True, format="mixed"
        ).dropna()
        return dt.max().strftime("%d/%m/%Y") if not dt.empty else None
    except Exception as e:
        logger.error("_ngay_so_lieu_max: lỗi parse ngày số liệu — %s", e, exc_info=True)
        return None


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
    ngay_sl = _ngay_so_lieu_max(df_full)

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

    df[COT_MA_CHUONG_TRINH] = (
        pd.to_numeric(df[COT_MA_CHUONG_TRINH], errors="coerce")
        .apply(lambda x: str(int(x)) if pd.notna(x) else "0")
    )

    def _norm_nv(v):
        # 1.0 → "1", 2.0 → "2", "ALL" → "ALL"
        try:
            return str(int(float(v)))
        except (ValueError, TypeError):
            return str(v).strip().upper()

    df[COT_NGUON_VON] = df[COT_NGUON_VON].map(_norm_nv)

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
        _clear_snapshot_cache()
        return KetQuaUpload(True, f"✅ Đã lưu snapshot kỳ **{ky}** ({so_dong} dòng tổng hợp)")
    except Exception as e:
        logger.error("luu_snapshot: thất bại kỳ=%s — %s", ky, e, exc_info=True)
        db.ghi_audit(username, "luu_snapshot_loi", str(e))
        return KetQuaUpload(False, f"❌ Lỗi lưu snapshot: {e}")


@st.cache_data(ttl=300, show_spinner=False)
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


@st.cache_data(ttl=300, show_spinner=False)
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


@st.cache_data(ttl=300, show_spinner=False)
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


def ky_baseline(ds_ky: list[str], ky_hien_tai: str | None = None) -> str | None:
    """Kỳ baseline: YYYY-12 năm trước của ky_hien_tai.

    Ưu tiên: (1) kỳ YYYY-12 chính xác, (2) kỳ gần nhất ≤ mốc, (3) kỳ cũ nhất.
    ds_ky phải được sort giảm dần (mới → cũ) như danh_sach_ky() trả về.
    """
    if not ds_ky:
        return None
    if ky_hien_tai is None:
        ky_hien_tai = ds_ky[0]
    try:
        nam = int(str(ky_hien_tai).split("-")[0])
    except (ValueError, IndexError):
        return ds_ky[-1]
    moc = f"{nam - 1}-12"
    if moc in ds_ky:
        return moc
    for ky in ds_ky:          # ds_ky sorted DESC → dừng tại kỳ đầu tiên ≤ mốc
        if ky <= moc:
            return ky
    return ds_ky[-1]           # fallback: kỳ cũ nhất


def _tong_hop_uy_thac_snapshot(
    df: pd.DataFrame,
    group_cols: list[str],
    cap_tong_hop: str,
) -> list[tuple]:
    """Tổng hợp một cấp snapshot từ HSTD đã lọc hồ sơ có ĐVUT."""
    groups = [((), df)] if not group_cols else df.groupby(group_cols, dropna=False, sort=False)
    rows: list[tuple] = []
    for keys, grp in groups:
        if not isinstance(keys, tuple):
            keys = (keys,)
        dims = dict(zip(group_cols, keys))
        to_cols = [c for c in [COT_TEN_PGD, COT_TEN_XA, COT_TEN_TO] if c in grp.columns]
        so_to = int(grp[to_cols].dropna(subset=[COT_TEN_TO]).drop_duplicates().shape[0]) if COT_TEN_TO in to_cols else 0
        rows.append((
            cap_tong_hop,
            str(dims.get(COT_TEN_PGD, "__ALL__")),
            str(dims.get(COT_TEN_XA, "__ALL__")),
            str(dims.get(COT_DVUT, "__ALL__")),
            str(dims.get(COT_TEN_TO, "__ALL__")),
            float(grp[COT_TONG_DU_NO].sum()),
            float(grp[COT_DU_NO_QH].sum()),
            float(grp["__lai_ton__"].sum()),
            float(grp[COT_SO_DU_TG].sum()),
            int(grp[COT_MA_KH].dropna().nunique()),
            int(grp[COT_SO_KU].dropna().nunique()),
            so_to,
        ))
    return rows


def luu_uy_thac_snapshot(
    df_full: pd.DataFrame,
    username: str,
    ky: str | None = None,
) -> KetQuaUpload:
    """Lưu snapshot ủy thác theo cấp CN/PGD/XA/HOI/TO, upsert-safe."""
    if df_full is None or df_full.empty or COT_DVUT not in df_full.columns:
        return KetQuaUpload(False, "Không có dữ liệu ĐVUT để tạo snapshot ủy thác.")
    ky_str = str(ky or "").strip() or _ky_tu_df(df_full)
    ngay_sl = _ngay_so_lieu_max(df_full)

    df = df_full.copy()
    df[COT_DVUT] = df[COT_DVUT].astype("string").str.strip().replace("", pd.NA)
    df = df[df[COT_DVUT].notna()].copy()
    if df.empty:
        return KetQuaUpload(False, "HSTD không có hồ sơ ủy thác hợp lệ.")
    for col in [COT_TONG_DU_NO, COT_DU_NO_QH, COT_LAI_TON, COT_LAI_TON_QH, COT_SO_DU_TG]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    for col in [COT_MA_KH, COT_SO_KU, COT_TEN_PGD, COT_TEN_XA, COT_TEN_TO]:
        if col not in df.columns:
            df[col] = pd.NA
    df["__lai_ton__"] = df[COT_LAI_TON] + df[COT_LAI_TON_QH]

    specs = [
        ("CN", []),
        ("PGD", [COT_TEN_PGD]),
        ("XA", [COT_TEN_PGD, COT_TEN_XA]),
        ("HOI", [COT_DVUT]),
        ("HOI", [COT_TEN_PGD, COT_DVUT]),
        ("TO", [COT_TEN_PGD, COT_TEN_XA, COT_DVUT, COT_TEN_TO]),
    ]
    rows: list[tuple] = []
    for cap, cols in specs:
        rows.extend(_tong_hop_uy_thac_snapshot(df, cols, cap))

    sql = """INSERT OR REPLACE INTO uy_thac_snapshot
             (ky, cap_tong_hop, ten_pgd, ten_xa, dvut, ten_to,
              tong_du_no, du_no_qh, lai_ton, so_du_tg, so_kh, so_ku, so_to,
              ngay_so_lieu, created_by)
             VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""
    try:
        with db.get_conn() as conn:
            conn.executemany(sql, [(ky_str, *row, ngay_sl, username) for row in rows])
            conn.commit()
        db.ghi_audit(username, "luu_uy_thac_snapshot", f"Kỳ {ky_str} — {len(rows)} dòng")
        _clear_snapshot_cache()
        return KetQuaUpload(True, f"✅ Đã lưu snapshot ủy thác kỳ **{ky_str}** ({len(rows)} dòng)")
    except Exception as e:
        logger.error("luu_uy_thac_snapshot: kỳ=%s — %s", ky_str, e, exc_info=True)
        db.ghi_audit(username, "luu_uy_thac_snapshot_loi", f"Kỳ {ky_str} — {e}")
        return KetQuaUpload(False, f"❌ Lỗi lưu snapshot ủy thác: {e}")


@st.cache_data(ttl=300, show_spinner=False)
def danh_sach_ky_uy_thac() -> list[str]:
    try:
        with db.get_conn() as conn:
            rows = conn.execute("SELECT DISTINCT ky FROM uy_thac_snapshot ORDER BY ky DESC").fetchall()
        return [r["ky"] for r in rows]
    except Exception as e:
        logger.error("danh_sach_ky_uy_thac: %s", e, exc_info=True)
        return []


@st.cache_data(ttl=300, show_spinner=False)
def doc_uy_thac_snapshot_multi(
    ky_list: tuple,
    ten_pgd: str | None = None,
    cap_tong_hop: str | None = None,
    ten_xa: str | None = None,
    dvut: str | None = None,
) -> pd.DataFrame:
    """Đọc chuỗi snapshot ủy thác theo CN/PGD/XA/HOI.

    Tương thích ngược:
    - Không truyền gì thêm -> CN
    - Truyền ten_pgd -> PGD
    - Truyền dvut nhưng không truyền ten_pgd -> HOI toàn CN (`ten_pgd='__ALL__'`)
    - Truyền dvut + ten_pgd -> HOI theo từng PGD
    """
    if not ky_list:
        return pd.DataFrame()

    cap = str(cap_tong_hop or "").strip().upper()
    if not cap:
        if dvut:
            cap = "HOI"
        elif ten_xa:
            cap = "XA"
        elif ten_pgd:
            cap = "PGD"
        else:
            cap = "CN"

    placeholders = ",".join("?" * len(ky_list))
    where_clauses = [f"cap_tong_hop=? AND ky IN ({placeholders})"]
    params: list[object] = [cap, *list(ky_list)]

    if cap == "HOI" and not ten_pgd:
        where_clauses.append("ten_pgd=?")
        params.append("__ALL__")
    elif ten_pgd and cap in {"PGD", "XA", "HOI", "TO"}:
        where_clauses.append("ten_pgd=?")
        params.append(ten_pgd)
    if ten_xa and cap in {"XA", "TO"}:
        where_clauses.append("ten_xa=?")
        params.append(ten_xa)
    if dvut and cap in {"HOI", "TO"}:
        where_clauses.append("dvut=?")
        params.append(dvut)

    try:
        with db.get_conn() as conn:
            rows = conn.execute(
                f"""SELECT ky, cap_tong_hop, ten_pgd, ten_xa, dvut, ten_to,
                            tong_du_no, du_no_qh, lai_ton, so_du_tg,
                            so_kh, so_ku, so_to, ngay_so_lieu
                     FROM uy_thac_snapshot
                     WHERE {' AND '.join(where_clauses)}
                     ORDER BY ky""",
                params,
            ).fetchall()
        return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()
    except Exception as e:
        logger.error("doc_uy_thac_snapshot_multi: %s", e, exc_info=True)
        return pd.DataFrame()


def doc_uy_thac_snapshot_hoi_cn(ky_list: tuple, dvut: str) -> pd.DataFrame:
    """Đọc chuỗi snapshot của một Hội ở grain toàn Chi nhánh."""
    if not str(dvut or "").strip():
        return pd.DataFrame()
    return doc_uy_thac_snapshot_multi(
        ky_list,
        cap_tong_hop="HOI",
        dvut=dvut,
    )


def doc_uy_thac_snapshot_hoi_pgd(
    ky_list: tuple,
    ten_pgd: str,
    dvut: str,
) -> pd.DataFrame:
    """Đọc chuỗi snapshot của một Hội trong đúng một PGD."""
    if not str(ten_pgd or "").strip() or not str(dvut or "").strip():
        return pd.DataFrame()
    return doc_uy_thac_snapshot_multi(
        ky_list,
        ten_pgd=ten_pgd,
        cap_tong_hop="HOI",
        dvut=dvut,
    )


@st.cache_data(ttl=300, show_spinner=False)
def doc_snapshot_theo_ct(ky: str) -> pd.DataFrame:
    """Cộng các dòng chi tiết PGD thành tổng theo chương trình của toàn CN.

    Trả về DataFrame cột: ma_ct, tong_du_no, du_no_th, du_no_qh, du_no_khoanh,
    so_ho, so_ku, gn_nam — sort by tong_du_no DESC.
    Dùng cho phân tích chiều chương trình tín dụng.
    """
    try:
        with db.get_conn() as conn:
            rows = conn.execute(
                """SELECT ma_ct,
                          SUM(tong_du_no)   AS tong_du_no,
                          SUM(du_no_th)     AS du_no_th,
                          SUM(du_no_qh)     AS du_no_qh,
                          SUM(du_no_khoanh) AS du_no_khoanh,
                          SUM(so_ho)        AS so_ho,
                          SUM(so_ku)        AS so_ku,
                          SUM(gn_nam)       AS gn_nam
                   FROM hstd_snapshot
                   WHERE ky=? AND ten_pgd!='__CN__' AND ma_ct!='ALL'
                   GROUP BY ma_ct
                   ORDER BY tong_du_no DESC""",
                (ky,)
            ).fetchall()
        return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()
    except Exception as e:
        logger.error("doc_snapshot_theo_ct: lỗi kỳ %s — %s", ky, e, exc_info=True)
        return pd.DataFrame()


@st.cache_data(ttl=300, show_spinner=False)
def doc_snapshot_multi(ky_list: tuple) -> pd.DataFrame:
    """Tổng toàn CN cho danh sách kỳ tùy chọn.

    Nhận tuple (để cache hoạt động đúng), trả về DataFrame cột:
    ky, tong_du_no, du_no_th, du_no_qh, du_no_khoanh, so_ho, so_ku, gn_nam, ngay_so_lieu
    sort by ky ASC.
    Gọi: doc_snapshot_multi(tuple(ky_list))
    """
    if not ky_list:
        return pd.DataFrame()
    try:
        placeholders = ",".join("?" * len(ky_list))
        with db.get_conn() as conn:
            rows = conn.execute(
                f"""SELECT ky, tong_du_no, du_no_th, du_no_qh, du_no_khoanh,
                           so_ho, so_ku, gn_nam, ngay_so_lieu
                    FROM hstd_snapshot
                    WHERE ten_pgd='__CN__' AND ma_ct='ALL' AND nguon_von='ALL'
                      AND ky IN ({placeholders})
                    ORDER BY ky ASC""",
                list(ky_list),
            ).fetchall()
        return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()
    except Exception as e:
        logger.error("doc_snapshot_multi: lỗi — %s", e, exc_info=True)
        return pd.DataFrame()


@st.cache_data(ttl=300, show_spinner=False)
def doc_snapshot_nvdp_range(tu_ky: str, den_ky: str) -> pd.DataFrame:
    """TW vs ĐP breakdown qua nhiều kỳ — dùng cho tab Nguồn vốn địa phương.

    Trả về DataFrame cột: ky, nguon_von ('1'|'2'), tong_du_no
    Sort by ky ASC. Aggregate từ tất cả PGD (bỏ qua dòng __CN__ và ALL).
    """
    try:
        with db.get_conn() as conn:
            rows = conn.execute(
                """SELECT ky, nguon_von, SUM(tong_du_no) AS tong_du_no
                   FROM hstd_snapshot
                   WHERE nguon_von IN ('1', '2')
                     AND ma_ct != 'ALL'
                     AND ten_pgd != '__CN__'
                     AND ky BETWEEN ? AND ?
                   GROUP BY ky, nguon_von
                   ORDER BY ky ASC""",
                (tu_ky, den_ky),
            ).fetchall()
        if not rows:
            return pd.DataFrame()
        result = pd.DataFrame([dict(r) for r in rows])
        result["tong_du_no"] = pd.to_numeric(result["tong_du_no"], errors="coerce").fillna(0.0)
        return result
    except Exception as e:
        logger.error("doc_snapshot_nvdp_range: lỗi — %s", e, exc_info=True)
        return pd.DataFrame()


@st.cache_data(ttl=300, show_spinner=False)
def doc_snapshot_nvdp_theo_pgd(ky: str) -> pd.DataFrame:
    """TW vs ĐP breakdown theo từng PGD của 1 kỳ.

    Trả về DataFrame cột: ten_pgd, nguon_von ('1'|'2'), tong_du_no.
    Dùng cho heatmap / delta PGD trong tab Nguồn vốn địa phương.
    """
    try:
        with db.get_conn() as conn:
            rows = conn.execute(
                """SELECT ten_pgd, nguon_von, SUM(tong_du_no) AS tong_du_no
                   FROM hstd_snapshot
                   WHERE ky=? AND nguon_von IN ('1', '2')
                     AND ma_ct != 'ALL'
                     AND ten_pgd != '__CN__'
                   GROUP BY ten_pgd, nguon_von
                   ORDER BY ten_pgd""",
                (ky,),
            ).fetchall()
        if not rows:
            return pd.DataFrame()
        result = pd.DataFrame([dict(r) for r in rows])
        result["tong_du_no"] = pd.to_numeric(result["tong_du_no"], errors="coerce").fillna(0.0)
        return result
    except Exception as e:
        logger.error("doc_snapshot_nvdp_theo_pgd: lỗi kỳ %s — %s", ky, e, exc_info=True)
        return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# NQ11 SNAPSHOT
# ─────────────────────────────────────────────────────────────────────────────

def _ky_tu_nq11(df: pd.DataFrame) -> str:
    """Suy ra kỳ 'YYYY-MM' từ cột Ngày báo cáo của NQ11."""
    try:
        from config import COT_NQ11_NGAY_BC
        return _suy_ra_ky(df, COT_NQ11_NGAY_BC)
    except Exception as e:
        logger.error("_ky_tu_nq11: lỗi suy ra kỳ — %s", e, exc_info=True)
    return datetime.now().strftime("%Y-%m")


def luu_nq11_snapshot(df_nq11: pd.DataFrame, username: str, ky: str | None = None) -> KetQuaUpload:
    """Tổng hợp df_nq11 (NQ11 toàn CN) → lưu vào nq11_snapshot.
    INSERT OR REPLACE — chạy lại cùng kỳ sẽ ghi đè.
    Lưu 2 loại: tổng theo PGD + tổng CN ('__CN__').

    ky: nếu cung cấp (vd "2025-12"), dùng trực tiếp.
        Nếu None, trích xuất từ cột "Ngày báo cáo NQ11".
        Fallback: tháng hiện tại.
    """
    if df_nq11 is None or df_nq11.empty:
        return KetQuaUpload(False, "Không có dữ liệu NQ11 để tạo snapshot.")

    from config import (
        COT_TEN_PGD, COT_DNO_NQ11, COT_NQ11_NO_TH, COT_NQ11_NO_QH,
        COT_NQ11_MA_KH, COT_NQ11_SO_TIEN_GN, COT_NQ11_NGAY_BC,
        DON_VI_CHI_NHANH,
    )

    if ky is None:
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

    # Chỉ giữ dòng còn dư nợ — so_kh phản ánh KH đang nợ thực, không đếm đã tất toán
    df = df[df[COT_DNO_NQ11] > 0].copy()

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
        _clear_snapshot_cache()
        return KetQuaUpload(True, f"✅ Đã lưu NQ11 snapshot kỳ **{ky}** ({so_dong} dòng)")
    except Exception as e:
        logger.error("luu_nq11_snapshot: thất bại kỳ=%s — %s", ky, e, exc_info=True)
        return KetQuaUpload(False, f"❌ Lỗi lưu NQ11 snapshot: {e}")


@st.cache_data(ttl=300, show_spinner=False)
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


@st.cache_data(ttl=300, show_spinner=False)
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

def _ky_tu_gqvl(df: pd.DataFrame) -> str:
    """Suy ra kỳ 'YYYY-MM' từ dữ liệu GQVL. Thử cột 'Ngày vay', fallback: tháng hiện tại."""
    return _suy_ra_ky(df, "Ngày vay")


def luu_gqvl_snapshot(df_gqvl: pd.DataFrame, username: str, ky: str | None = None) -> KetQuaUpload:
    """Tổng hợp df_gqvl (GQVL toàn CN, sau khi đã rename cột) → lưu vào gqvl_snapshot.
    INSERT OR REPLACE — chạy lại cùng kỳ sẽ ghi đè.
    Lưu 2 loại: tổng theo PGD + tổng CN ('__CN__').

    ky: nếu cung cấp (vd "2025-12"), dùng trực tiếp.
        Nếu None, thử trích xuất từ cột "Ngày vay" trong dữ liệu.
        Fallback: tháng hiện tại.
    """
    if df_gqvl is None or df_gqvl.empty:
        return KetQuaUpload(False, "Không có dữ liệu GQVL để tạo snapshot.")

    from config import COT_TEN_PGD, DON_VI_CHI_NHANH

    _COL_TH    = "Dư nợ trong hạn"
    _COL_QH    = "Dư nợ quá hạn"
    _COL_KH    = "Dư nợ khoanh"
    _COL_MA_KH = "Mã KH"
    _COL_GN    = COT_GIAI_NGAN_TRONG_NAM

    if ky is None:
        ky = _ky_tu_gqvl(df_gqvl)

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
        _clear_snapshot_cache()
        return KetQuaUpload(True, f"✅ Đã lưu GQVL snapshot kỳ **{ky}** ({so_dong} dòng)")
    except Exception as e:
        logger.error("luu_gqvl_snapshot: thất bại kỳ=%s — %s", ky, e, exc_info=True)
        return KetQuaUpload(False, f"❌ Lỗi lưu GQVL snapshot: {e}")


@st.cache_data(ttl=300, show_spinner=False)
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


@st.cache_data(ttl=300, show_spinner=False)
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

    from data.cdtotkvv import chuan_hoa_cdtotkvv_phan_tich

    df_src = chuan_hoa_cdtotkvv_phan_tich(df_cdtotkvv)
    if df_src.empty:
        return KetQuaUpload(False, "Không có Tổ CDTOTKVV còn dư nợ để tạo snapshot.")
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
        df_pgd[col_name] = pd.to_numeric(df_pgd[col_name], errors="coerce").fillna(0).astype(int)

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
        _clear_snapshot_cache()
        return KetQuaUpload(True, f"✅ Đã lưu CDTOTKVV snapshot kỳ **{ky}** ({so_dong} dòng)")
    except Exception as e:
        logger.error("luu_cdtotkvv_snapshot: thất bại kỳ=%s — %s", ky, e, exc_info=True)
        return KetQuaUpload(False, f"❌ Lỗi lưu CDTOTKVV snapshot: {e}")


@st.cache_data(ttl=300, show_spinner=False)
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


@st.cache_data(ttl=300, show_spinner=False)
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


def compare_snapshot_2_ky(ky1: str, ky2: str, table: str = "hstd") -> pd.DataFrame:
    """So sánh hai kỳ snapshot HSTD theo ten_pgd, có sẵn cột delta và pct."""
    table_key = str(table or "hstd").strip().lower()
    if table_key != "hstd":
        raise ValueError("compare_snapshot_2_ky hiện chỉ hỗ trợ table='hstd'")

    df1 = doc_snapshot(ky1).copy()
    df2 = doc_snapshot(ky2).copy()
    if df1.empty or df2.empty:
        return pd.DataFrame()

    cols = [
        "ten_pgd", "tong_du_no", "du_no_th", "du_no_qh", "du_no_khoanh",
        "so_ho", "so_ku", "gn_nam", "ngay_so_lieu",
    ]
    for df in (df1, df2):
        for col in cols:
            if col not in df.columns:
                df[col] = 0 if col != "ten_pgd" else ""

    merged = df2[cols].merge(
        df1[cols],
        on="ten_pgd",
        suffixes=("", "_prev"),
        how="outer",
    )
    for col in ["tong_du_no", "du_no_th", "du_no_qh", "du_no_khoanh", "so_ho", "so_ku", "gn_nam"]:
        prev_col = f"{col}_prev"
        merged[col] = pd.to_numeric(merged[col], errors="coerce").fillna(0)
        merged[prev_col] = pd.to_numeric(merged[prev_col], errors="coerce").fillna(0)
        merged[f"{col}_delta"] = merged[col] - merged[prev_col]
        denom = merged[prev_col].replace(0, pd.NA)
        merged[f"{col}_pct"] = (merged[f"{col}_delta"] / denom * 100).fillna(0)

    merged["ky_prev"] = ky1
    merged["ky"] = ky2
    return merged.sort_values("ten_pgd").reset_index(drop=True)


def validate_snapshot(ky: str) -> dict:
    """Kiểm tra tính nhất quán cơ bản của HSTD snapshot một kỳ."""
    issues: list[str] = []
    df = doc_snapshot(ky)
    if df.empty:
        return {"ok": False, "issues": [f"Không có HSTD snapshot kỳ {ky}"]}

    df = df.copy()
    numeric_cols = ["tong_du_no", "du_no_th", "du_no_qh", "du_no_khoanh", "so_ho", "so_ku", "gn_nam"]
    for col in numeric_cols:
        if col not in df.columns:
            issues.append(f"Thiếu cột {col}")
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df_cn = df[df["ten_pgd"].astype(str) == "__CN__"]
    df_pgd = df[df["ten_pgd"].astype(str) != "__CN__"]
    if df_cn.empty:
        issues.append("Thiếu dòng tổng Chi nhánh (__CN__)")
    else:
        cn = df_cn.iloc[0]
        for col in numeric_cols:
            delta = abs(float(cn[col]) - float(df_pgd[col].sum()))
            tolerance = 1.0 if col in {"tong_du_no", "du_no_th", "du_no_qh", "du_no_khoanh", "gn_nam"} else 0.0
            if delta > tolerance:
                issues.append(f"Tổng CN cột {col} lệch {delta:,.0f} so với tổng PGD")

    for col in numeric_cols:
        if (df[col] < 0).any():
            issues.append(f"Cột {col} có giá trị âm")

    pgd_hien_co = set(df_pgd["ten_pgd"].astype(str))
    missing = [pgd for pgd in DS_PGD if pgd not in pgd_hien_co]
    if missing:
        issues.append(f"Thiếu dữ liệu {len(missing)}/{len(DS_PGD)} PGD: {', '.join(missing[:5])}")

    return {"ok": not issues, "issues": issues}


def export_snapshot_excel(ky_list: list[str] | tuple[str, ...], loai: str = "hstd") -> bytes:
    """Xuất snapshot nhiều kỳ ra Excel, mỗi kỳ một sheet."""
    loai_key = str(loai or "hstd").strip().lower()
    table_map = {
        "hstd": "hstd_snapshot",
        "uy_thac": "uy_thac_snapshot",
        "nq11": "nq11_snapshot",
        "gqvl": "gqvl_snapshot",
        "cdtotkvv": "cdtotkvv_snapshot",
    }
    if loai_key not in table_map:
        raise ValueError(f"Loại snapshot không hỗ trợ: {loai}")

    sheets: dict[str, pd.DataFrame] = {}
    table_name = table_map[loai_key]
    for ky in ky_list:
        ky_str = str(ky)
        try:
            with db.get_conn() as conn:
                rows = conn.execute(
                    f"SELECT * FROM {table_name} WHERE ky=? ORDER BY ten_pgd",
                    (ky_str,),
                ).fetchall()
            df = pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()
            if "id" in df.columns:
                df = df.drop(columns=["id"])
        except Exception as e:
            logger.error("export_snapshot_excel: lỗi đọc %s kỳ %s — %s", loai_key, ky_str, e, exc_info=True)
            df = pd.DataFrame({"Lỗi": [str(e)]})
        sheets[f"{loai_key}_{ky_str}".replace("-", "_")[:31]] = df

    from utils import xuat_excel
    return xuat_excel(sheets or {"Snapshot": pd.DataFrame()})


def _clear_snapshot_cache() -> None:
    """Clear riêng các cache snapshot, tránh xóa cache dữ liệu khác của app."""
    for fn in (
        doc_snapshot,
        doc_snapshot_range,
        danh_sach_ky,
        doc_snapshot_theo_ct,
        doc_snapshot_multi,
        doc_snapshot_nvdp_range,
        danh_sach_ky_uy_thac,
        doc_uy_thac_snapshot_multi,
        doc_nq11_snapshot,
        danh_sach_ky_nq11,
        doc_gqvl_snapshot,
        danh_sach_ky_gqvl,
        doc_cdtotkvv_snapshot,
        danh_sach_ky_cdtotkvv,
    ):
        if hasattr(fn, "clear"):
            try:
                fn.clear()
            except Exception as e:
                logger.error("_clear_snapshot_cache: không clear được %s — %s", getattr(fn, "__name__", fn), e, exc_info=True)


_SNAPSHOT_TABLES = (
    "hstd_snapshot",
    "uy_thac_snapshot",
    "nq11_snapshot",
    "gqvl_snapshot",
    "cdtotkvv_snapshot",
)


def xoa_snapshot(ky: str, username: str) -> None:
    try:
        with db.get_conn() as conn:
            for table in _SNAPSHOT_TABLES:
                conn.execute(f"DELETE FROM {table} WHERE ky=?", (ky,))
            conn.commit()
        db.ghi_audit(username, "xoa_snapshot", f"Đã xóa snapshot kỳ {ky} (5 bảng)")
        _clear_snapshot_cache()
    except Exception as e:
        logger.error("xoa_snapshot: lỗi xóa snapshot kỳ %s — %s", ky, e, exc_info=True)
        db.ghi_audit(username, "xoa_snapshot_loi", str(e))
