"""So sánh số liệu giữa kỳ hiện tại và mốc 31/12 năm đã chọn."""
from __future__ import annotations

import os

import pandas as pd
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from auth import la_phan_he_cn, normalize_role
from config import (
    COT_DU_NO_QH,
    COT_DU_NO_TH,
    COT_MA_KH,
    COT_NGAY_SL,
    COT_PHAN_LOAI,
    COT_SO_KU,
    COT_TEN_PGD,
    COT_TONG_DU_NO,
    HSTD_DS_CHO_VAY_NAM_ALIASES,
    baseline_pgd_path,
    danh_sach_nam_baseline,
    danh_sach_nam_baseline_pgd,
)
from data.hstd import doc_baseline_merged
from data.pgd import pgd_slug
from services.hhi_service import danh_gia_hhi, tinh_hhi, tinh_hhi_breakdown
from services.migration_service import danh_sach_ky, doc_snapshot, migration_matrix
from utils import fmt_so, fmt_ty

COT_DU_NO_KHOANH = "Dư nợ khoanh"


def _agg_mot_pgd(df: pd.DataFrame) -> dict:
    """Tổng hợp các chỉ tiêu chính cho 1 DataFrame (1 PGD hoặc toàn CN)."""
    if df is None or df.empty:
        return {
            "tong_du_no": 0, "du_no_th": 0, "du_no_qh": 0,
            "du_no_khoanh": 0, "so_ho": 0, "so_ku": 0, "gn_nam": 0,
        }
    col_gn = next((c for c in HSTD_DS_CHO_VAY_NAM_ALIASES if c in df.columns), None)
    return {
        "tong_du_no":    df[COT_TONG_DU_NO].sum() if COT_TONG_DU_NO in df.columns else 0,
        "du_no_th":      df[COT_DU_NO_TH].sum()   if COT_DU_NO_TH   in df.columns else 0,
        "du_no_qh":      df[COT_DU_NO_QH].sum()   if COT_DU_NO_QH   in df.columns else 0,
        "du_no_khoanh":  df[COT_DU_NO_KHOANH].sum() if COT_DU_NO_KHOANH in df.columns else 0,
        "so_ho":         int(df[COT_MA_KH].nunique()) if COT_MA_KH in df.columns else 0,
        "so_ku":         int(df[COT_SO_KU].nunique()) if COT_SO_KU in df.columns else 0,
        "gn_nam":        df[col_gn].sum() if col_gn else 0,
    }


def _agg_theo_pgd(df: pd.DataFrame) -> pd.DataFrame:
    """Tổng hợp chỉ tiêu theo từng PGD, thêm hàng tổng."""
    if df is None or df.empty or COT_TEN_PGD not in df.columns:
        return pd.DataFrame()

    agg_spec: dict = {
        "tong_du_no": (COT_TONG_DU_NO, "sum"),
        "du_no_th":   (COT_DU_NO_TH, "sum"),
        "du_no_qh":   (COT_DU_NO_QH, "sum"),
        "so_ho":      (COT_MA_KH, "nunique"),
        "so_ku":      (COT_SO_KU, "nunique"),
    }
    if COT_DU_NO_KHOANH in df.columns:
        agg_spec["du_no_khoanh"] = (COT_DU_NO_KHOANH, "sum")
    col_gn = next((c for c in HSTD_DS_CHO_VAY_NAM_ALIASES if c in df.columns), None)
    if col_gn:
        agg_spec["gn_nam"] = (col_gn, "sum")

    try:
        result = df.groupby(COT_TEN_PGD).agg(**agg_spec).reset_index()
    except Exception:
        return pd.DataFrame()

    # Hàng tổng
    tong = {COT_TEN_PGD: "⬛ Tổng Chi nhánh"}
    for col in result.columns:
        if col != COT_TEN_PGD:
            tong[col] = result[col].sum()
    result = pd.concat([result, pd.DataFrame([tong])], ignore_index=True)
    return result


def _delta_str(val: float, baseline: float, unit: str = "ty") -> str:
    """Chuỗi ±delta ngắn gọn."""
    delta = val - baseline
    sign = "+" if delta >= 0 else ""
    if unit == "ty":
        return f"{sign}{fmt_ty(delta)}"
    return f"{sign}{fmt_so(int(delta))}"


def _tl_nqh(du_no_qh: float, tong_du_no: float) -> float:
    return (du_no_qh / tong_du_no * 100) if tong_du_no > 0 else 0.0


def _fmt_pct_vn(x: float) -> str:
    return f"{x:.2f}".replace(".", ",") + "%"


def _ma_tran_chuyen_nhuong(ky_truoc: str, ky_sau: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Lấy ma trận chuyển nhóm nợ từ snapshot."""
    matrix, chi_tiet = migration_matrix(ky_truoc, ky_sau)
    return matrix, chi_tiet


def _phan_loai_khach_hang(df_truoc: pd.DataFrame, df_sau: pd.DataFrame) -> pd.DataFrame:
    """Phân loại khách hàng: Retained, Churned, New, Reactivated."""
    if df_truoc.empty or df_sau.empty or COT_MA_KH not in df_truoc.columns:
        return pd.DataFrame()

    ma_kh_truoc = set(df_truoc[COT_MA_KH].astype(str).str.strip())
    ma_kh_sau = set(df_sau[COT_MA_KH].astype(str).str.strip())

    retained = len(ma_kh_truoc & ma_kh_sau)
    churned = len(ma_kh_truoc - ma_kh_sau)
    new = len(ma_kh_sau - ma_kh_truoc)

    return pd.DataFrame([{
        "Loại": "Tồn tại trước đó",
        "Số hộ": fmt_so(retained),
        "% KH trước": _fmt_pct_vn((retained / len(ma_kh_truoc) * 100) if ma_kh_truoc else 0),
    }, {
        "Loại": "Rời khỏi",
        "Số hộ": fmt_so(churned),
        "% KH trước": _fmt_pct_vn((churned / len(ma_kh_truoc) * 100) if ma_kh_truoc else 0),
    }, {
        "Loại": "Mới",
        "Số hộ": fmt_so(new),
        "% KH sau": _fmt_pct_vn((new / len(ma_kh_sau) * 100) if ma_kh_sau else 0),
    }])


def _phan_tich_par(df: pd.DataFrame) -> pd.DataFrame:
    """Phân tích PAR (Portfolio at Risk) theo ngày quá hạn."""
    if df.empty or COT_DU_NO_QH not in df.columns:
        return pd.DataFrame()

    tong_qh = df[COT_DU_NO_QH].sum() if COT_DU_NO_QH in df.columns else 0
    tong_dn = df[COT_TONG_DU_NO].sum() if COT_TONG_DU_NO in df.columns else 0

    par = (tong_qh / tong_dn * 100) if tong_dn > 0 else 0.0

    return pd.DataFrame([{
        "Chỉ tiêu": "PAR (Portfolio At Risk)",
        "Dư nợ quá hạn": fmt_ty(tong_qh),
        "Tổng dư nợ": fmt_ty(tong_dn),
        "PAR %": _fmt_pct_vn(par),
    }])


def _phan_tich_hhi_pgd(df: pd.DataFrame) -> tuple[float, pd.DataFrame, str, str, str]:
    """Tính HHI theo PGD — nồng độ rủi ro."""
    if df.empty or COT_TEN_PGD not in df.columns or COT_TONG_DU_NO not in df.columns:
        return 0.0, pd.DataFrame(), "N/A", "", ""

    hhi = tinh_hhi(df, COT_TEN_PGD, COT_TONG_DU_NO)
    breakdown = tinh_hhi_breakdown(df, COT_TEN_PGD, COT_TONG_DU_NO)

    muc_do, icon, mau = danh_gia_hhi(hhi)

    return hhi, breakdown, muc_do, icon, mau


def _top_movers(
    df_ht: pd.DataFrame,
    df_bl: pd.DataFrame,
    nhom_by: str = COT_TEN_PGD,
    n: int = 5,
) -> pd.DataFrame:
    """Top N PGD với thay đổi lớn nhất về dư nợ và NQH."""
    if df_ht.empty or df_bl.empty:
        return pd.DataFrame()

    if nhom_by not in df_ht.columns or nhom_by not in df_bl.columns:
        return pd.DataFrame()

    agg_ht = df_ht.groupby(nhom_by).agg({
        COT_TONG_DU_NO: "sum",
        COT_DU_NO_QH: "sum",
    }).reset_index()
    agg_ht["nqh_pct"] = (agg_ht[COT_DU_NO_QH] / agg_ht[COT_TONG_DU_NO] * 100).fillna(0)

    agg_bl = df_bl.groupby(nhom_by).agg({
        COT_TONG_DU_NO: "sum",
        COT_DU_NO_QH: "sum",
    }).reset_index()
    agg_bl["nqh_pct"] = (agg_bl[COT_DU_NO_QH] / agg_bl[COT_TONG_DU_NO] * 100).fillna(0)

    merged = agg_ht.merge(
        agg_bl,
        on=nhom_by,
        how="outer",
        suffixes=("_ht", "_bl"),
    ).fillna(0)

    merged["delta_dn"] = merged[f"{COT_TONG_DU_NO}_ht"] - merged[f"{COT_TONG_DU_NO}_bl"]
    merged["delta_nqh"] = merged["nqh_pct_ht"] - merged["nqh_pct_bl"]
    merged["pct_change"] = (
        merged["delta_dn"] / merged[f"{COT_TONG_DU_NO}_bl"]
        * 100
    ).where(merged[f"{COT_TONG_DU_NO}_bl"] != 0, 0)

    top = merged.nlargest(n, "delta_dn")

    result = pd.DataFrame()
    result[nhom_by] = top[nhom_by]
    result["DN mốc"] = top[f"{COT_TONG_DU_NO}_bl"].apply(fmt_ty)
    result["DN HT"] = top[f"{COT_TONG_DU_NO}_ht"].apply(fmt_ty)
    result["Δ DN"] = top["delta_dn"].apply(lambda x: ("+" if x >= 0 else "") + fmt_ty(x))
    result["% Thay đổi"] = top["pct_change"].apply(_fmt_pct_vn)
    result["NQH mốc"] = top["nqh_pct_bl"].apply(_fmt_pct_vn)
    result["NQH HT"] = top["nqh_pct_ht"].apply(_fmt_pct_vn)

    return result


def render(tab: DeltaGenerator = None, **kwargs) -> None:
    df       = kwargs.get("df")
    df_full  = kwargs.get("df_full", df)
    role_raw = str(kwargs.get("role", "user") or "user")
    role     = normalize_role(role_raw)
    pgd_user = kwargs.get("pgd_user")
    pgd_mode = kwargs.get("pgd_mode", False)

    ctx = tab if tab is not None else st.container()

    # prefix để tránh DuplicateElementKey
    if pgd_mode and pgd_user:
        key_prefix = f"pgd_{pgd_slug(pgd_user)}_"
    else:
        key_prefix = "cn_"

    with ctx:
        st.subheader("📈 So sánh kỳ — Hiện tại vs Mốc 31/12")

        # ── Chọn năm baseline ─────────────────────────────────────────────
        ds_nam = danh_sach_nam_baseline_pgd() or danh_sach_nam_baseline()
        if not ds_nam:
            st.warning("⚠️ Chưa có dữ liệu năm trước để so sánh.")
            st.markdown(
                """
**Cách thêm dữ liệu mốc 31/12:**

1. Vào menu **Hệ thống → Upload dữ liệu**
2. Mở phần **📅 Upload mốc số liệu 31/12 (Baseline)**
3. Chọn năm (ví dụ: 2025) và upload file HSTD của ngày 31/12 năm đó
4. Quay lại tab này — dữ liệu so sánh sẽ hiện ra tự động

> File cần upload có định dạng giống file HSTD thường (sheet **BCQUERY**, header dòng 5).
                """
            )
            return

        chon_nam = st.selectbox(
            "So sánh với mốc 31/12 năm",
            ds_nam,
            key=f"{key_prefix}ssk_nam",
        )

        # ── Đọc baseline ──────────────────────────────────────────────────
        fp_check = baseline_pgd_path(pgd_user if pgd_user else "hoi_so", chon_nam)
        _ts = os.path.getmtime(fp_check) if os.path.exists(fp_check) else 0
        df_bl_full = doc_baseline_merged(chon_nam, _ts=_ts)

        if df_bl_full is None or df_bl_full.empty:
            st.warning(f"⚠️ Chưa có dữ liệu baseline 31/12/{chon_nam}.")
            return

        # Lọc theo PGD nếu là pgd_mode
        if pgd_mode and pgd_user and COT_TEN_PGD in df_bl_full.columns:
            df_bl = df_bl_full[df_bl_full[COT_TEN_PGD] == pgd_user].copy()
        else:
            df_bl = df_bl_full

        # df hiện tại
        df_ht = df if pgd_mode else df_full
        if df_ht is None or df_ht.empty:
            st.warning("⚠️ Chưa có dữ liệu HSTD hiện tại.")
            return

        # ── Tổng hợp toàn bộ ─────────────────────────────────────────────
        agg_ht = _agg_mot_pgd(df_ht)
        agg_bl = _agg_mot_pgd(df_bl)

        # Ngày số liệu hiện tại
        ngay_sl = ""
        if "Ngày số liệu" in df_ht.columns:
            sl = df_ht["Ngày số liệu"].dropna()
            if len(sl):
                ngay_sl = str(sl.iloc[0])

        st.caption(
            f"**Kỳ hiện tại:** {ngay_sl or 'N/A'} &nbsp;|&nbsp; "
            f"**Mốc so sánh:** 31/12/{chon_nam}"
        )
        st.divider()

        # ═══════════ KPI CARDS ════════════════════════════════════════════
        st.markdown("**📊 Chỉ tiêu tổng hợp**")
        k1, k2, k3, k4 = st.columns(4)

        tl_nqh_ht = _tl_nqh(agg_ht["du_no_qh"], agg_ht["tong_du_no"])
        tl_nqh_bl = _tl_nqh(agg_bl["du_no_qh"], agg_bl["tong_du_no"])

        k1.metric(
            "Tổng dư nợ",
            fmt_ty(agg_ht["tong_du_no"]),
            delta=_delta_str(agg_ht["tong_du_no"], agg_bl["tong_du_no"]),
            help=f"Mốc 31/12/{chon_nam}: {fmt_ty(agg_bl['tong_du_no'])}",
        )
        k2.metric(
            "Dư nợ quá hạn",
            fmt_ty(agg_ht["du_no_qh"]),
            delta=_delta_str(agg_ht["du_no_qh"], agg_bl["du_no_qh"]),
            delta_color="inverse",
            help=f"Mốc 31/12/{chon_nam}: {fmt_ty(agg_bl['du_no_qh'])}",
        )
        k3.metric(
            "Tỷ lệ NQH",
            _fmt_pct_vn(tl_nqh_ht),
            delta=_fmt_pct_vn(tl_nqh_ht - tl_nqh_bl),
            delta_color="inverse",
            help=f"Mốc 31/12/{chon_nam}: {_fmt_pct_vn(tl_nqh_bl)}",
        )
        k4.metric(
            "Số hộ vay",
            fmt_so(agg_ht["so_ho"]),
            delta=_delta_str(agg_ht["so_ho"], agg_bl["so_ho"], unit="so"),
            help=f"Mốc 31/12/{chon_nam}: {fmt_so(agg_bl['so_ho'])}",
        )

        st.divider()

        # ── Chỉ tiêu chi tiết ─────────────────────────────────────────────
        with st.expander("📋 Chi tiết chỉ tiêu", expanded=True):
            rows = [
                ("Tổng dư nợ",         agg_bl["tong_du_no"],   agg_ht["tong_du_no"],   "ty"),
                ("  Dư nợ trong hạn",  agg_bl["du_no_th"],     agg_ht["du_no_th"],     "ty"),
                ("  Dư nợ quá hạn",    agg_bl["du_no_qh"],     agg_ht["du_no_qh"],     "ty"),
                ("  Dư nợ khoanh",     agg_bl["du_no_khoanh"], agg_ht["du_no_khoanh"], "ty"),
                ("Giải ngân trong năm",agg_bl["gn_nam"],       agg_ht["gn_nam"],       "ty"),
                ("Số hộ vay",          agg_bl["so_ho"],        agg_ht["so_ho"],        "so"),
                ("Số khế ước",         agg_bl["so_ku"],        agg_ht["so_ku"],        "so"),
            ]
            data_ct = []
            for ten, bl_val, ht_val, unit in rows:
                delta = ht_val - bl_val
                pct = (delta / bl_val * 100) if bl_val != 0 else 0.0
                sign = "+" if delta >= 0 else ""
                data_ct.append({
                    "Chỉ tiêu": ten,
                    f"Mốc 31/12/{chon_nam}": fmt_ty(bl_val) if unit == "ty" else fmt_so(int(bl_val)),
                    "Hiện tại":              fmt_ty(ht_val) if unit == "ty" else fmt_so(int(ht_val)),
                    "Chênh lệch":            f"{sign}{fmt_ty(delta)}" if unit == "ty" else f"{sign}{fmt_so(int(delta))}",
                    "% thay đổi":            f"{sign}{pct:.2f}".replace(".", ",") + "%",
                })
            df_ct = pd.DataFrame(data_ct)
            st.dataframe(df_ct, hide_index=True, use_container_width=True)

        # ═══════════ BẢNG THEO PGD (chỉ CN role) ═════════════════════════
        if la_phan_he_cn(role) and not pgd_mode:
            st.divider()
            st.markdown("**🗺️ Chi tiết theo PGD**")

            df_pgd_ht = _agg_theo_pgd(df_full)
            df_pgd_bl = _agg_theo_pgd(df_bl_full)

            if df_pgd_ht.empty or df_pgd_bl.empty:
                st.info("Không đủ dữ liệu để so sánh theo PGD.")
                return

            # Merge theo tên PGD
            df_merge = df_pgd_ht.merge(
                df_pgd_bl,
                on=COT_TEN_PGD,
                how="outer",
                suffixes=("_ht", "_bl"),
            ).fillna(0)

            # Tính delta
            df_merge["Δ Dư nợ"] = df_merge["tong_du_no_ht"] - df_merge["tong_du_no_bl"]
            df_merge["Δ DN %"]  = df_merge.apply(
                lambda r: (r["Δ Dư nợ"] / r["tong_du_no_bl"] * 100) if r["tong_du_no_bl"] != 0 else 0.0,
                axis=1,
            )
            df_merge["NQH mốc"] = df_merge.apply(
                lambda r: _tl_nqh(r["du_no_qh_bl"], r["tong_du_no_bl"]), axis=1
            )
            df_merge["NQH HT"] = df_merge.apply(
                lambda r: _tl_nqh(r["du_no_qh_ht"], r["tong_du_no_ht"]), axis=1
            )
            df_merge["Δ NQH"] = df_merge["NQH HT"] - df_merge["NQH mốc"]
            df_merge["Δ Hộ"]  = (df_merge["so_ho_ht"] - df_merge["so_ho_bl"]).astype(int)

            # Cột hiển thị — format kiểu VN
            cols_show = {
                COT_TEN_PGD:                        "Tên PGD",
                f"DN mốc 31/12/{chon_nam}":         "DN mốc 31/12",
                "DN hiện tại":                      "DN hiện tại",
                "±DN":                              "±DN",
                "±DN%":                             "±DN%",
                f"Hộ mốc 31/12/{chon_nam}":         "Hộ mốc 31/12",
                "Hộ HT":                            "Hộ HT",
                "±Hộ":                              "±Hộ",
                "NQH mốc":                          "NQH mốc",
                "NQH HT":                           "NQH HT",
                "±NQH":                             "±NQH",
            }
            df_out = pd.DataFrame()
            df_out["Tên PGD"]                    = df_merge[COT_TEN_PGD]
            df_out[f"DN mốc 31/12/{chon_nam}"]   = df_merge["tong_du_no_bl"].apply(fmt_ty)
            df_out["DN hiện tại"]                = df_merge["tong_du_no_ht"].apply(fmt_ty)
            df_out["±DN"]                        = df_merge["Δ Dư nợ"].apply(
                lambda x: ("+" if x >= 0 else "") + fmt_ty(x)
            )
            df_out["±DN%"] = df_merge["Δ DN %"].apply(
                lambda x: ("+" if x >= 0 else "") + f"{x:.2f}".replace(".", ",") + "%"
            )
            df_out[f"Hộ mốc 31/12/{chon_nam}"]  = df_merge["so_ho_bl"].apply(lambda x: fmt_so(int(x)))
            df_out["Hộ HT"]                     = df_merge["so_ho_ht"].apply(lambda x: fmt_so(int(x)))
            df_out["±Hộ"]                       = df_merge["Δ Hộ"].apply(
                lambda x: ("+" if x >= 0 else "") + fmt_so(x)
            )
            df_out["NQH mốc"]  = df_merge["NQH mốc"].apply(_fmt_pct_vn)
            df_out["NQH HT"]   = df_merge["NQH HT"].apply(_fmt_pct_vn)
            df_out["±NQH"] = df_merge["Δ NQH"].apply(
                lambda x: ("+" if x >= 0 else "") + _fmt_pct_vn(abs(x)).replace("%", "") + "%"
            )

            st.dataframe(df_out, hide_index=True, use_container_width=True, height=520)

        # ═══════════ MA TRẬN CHUYỂN NHÓM NỢ ═════════════════════════════════
        st.divider()
        with st.expander("📊 Ma trận chuyển nhóm nợ", expanded=False):
            kys = danh_sach_ky()
            if len(kys) >= 2:
                ky_map = {k: k for k in kys}
                ky_truoc = st.selectbox(
                    "Kỳ trước",
                    kys[1:],
                    key=f"{key_prefix}mm_ky_truoc",
                    format_func=lambda x: ky_map.get(x, x),
                )
                ky_sau = st.selectbox(
                    "Kỳ sau",
                    kys,
                    key=f"{key_prefix}mm_ky_sau",
                    format_func=lambda x: ky_map.get(x, x),
                )

                if ky_truoc and ky_sau and ky_truoc != ky_sau:
                    matrix, chi_tiet = _ma_tran_chuyen_nhuong(ky_truoc, ky_sau)
                    if not matrix.empty:
                        st.subheader(f"Ma trận: {ky_truoc} → {ky_sau}")
                        st.dataframe(matrix, use_container_width=True)

                        if not chi_tiet.empty:
                            with st.expander(
                                f"📋 Chi tiết ({len(chi_tiet)} khoản)",
                                expanded=False,
                            ):
                                st.dataframe(
                                    chi_tiet,
                                    hide_index=True,
                                    use_container_width=True,
                                    height=400,
                                )
                    else:
                        st.info("Không đủ dữ liệu snapshot để so sánh.")
            else:
                st.info("Cần ít nhất 2 kỳ để hiển thị ma trận chuyển nhóm nợ.")

        # ═══════════ PHÂN LOẠI KHÁCH HÀNG ═════════════════════════════════
        st.divider()
        with st.expander("👥 Phân loại khách hàng", expanded=False):
            st.markdown(
                "**Phân tích thay đổi nhóm khách hàng giữa hai kỳ:**"
            )
            df_lifecycle = _phan_loai_khach_hang(df_bl, df_ht)
            if not df_lifecycle.empty:
                st.dataframe(df_lifecycle, hide_index=True, use_container_width=True)
            else:
                st.info("Không đủ dữ liệu khách hàng để phân loại.")

        # ═══════════ PHÂN TÍCH PAR ═════════════════════════════════════════
        st.divider()
        with st.expander("🎯 Phân tích PAR (Portfolio at Risk)", expanded=False):
            st.markdown(
                "**Portfolio at Risk (PAR)** — tỷ lệ dư nợ quá hạn so với tổng dư nợ"
            )
            c1, c2 = st.columns(2)

            with c1:
                st.subheader("Mốc 31/12")
                df_par_bl = _phan_tich_par(df_bl)
                if not df_par_bl.empty:
                    st.dataframe(df_par_bl, hide_index=True, use_container_width=True)

            with c2:
                st.subheader("Hiện tại")
                df_par_ht = _phan_tich_par(df_ht)
                if not df_par_ht.empty:
                    st.dataframe(df_par_ht, hide_index=True, use_container_width=True)

        # ═══════════ PHÂN TÍCH HHI ═════════════════════════════════════════
        st.divider()
        with st.expander(
            "🎲 Phân tích tập trung rủi ro (HHI Index)", expanded=False
        ):
            st.markdown(
                "**Herfindahl-Hirschman Index (HHI)** — đo lường nồng độ rủi ro theo PGD"
            )
            c1, c2 = st.columns(2)

            with c1:
                st.subheader("Mốc 31/12")
                hhi_bl, bd_bl, muc_bl, icon_bl, mau_bl = _phan_tich_hhi_pgd(df_bl)
                col1, col2 = st.columns(2)
                col1.metric(
                    "HHI Score",
                    f"{hhi_bl * 10000:.0f}",
                    help="Thang 0–10000. Cao = rủi ro tập trung.",
                )
                col2.markdown(f"### {icon_bl} {muc_bl}")
                if not bd_bl.empty:
                    st.dataframe(
                        bd_bl[["du_no", "ty_trong_pct", "dong_gop_hhi"]],
                        hide_index=True,
                        use_container_width=True,
                        height=250,
                    )

            with c2:
                st.subheader("Hiện tại")
                hhi_ht, bd_ht, muc_ht, icon_ht, mau_ht = _phan_tich_hhi_pgd(df_ht)
                col1, col2 = st.columns(2)
                col1.metric(
                    "HHI Score",
                    f"{hhi_ht * 10000:.0f}",
                    help="Thang 0–10000. Cao = rủi ro tập trung.",
                )
                col2.markdown(f"### {icon_ht} {muc_ht}")
                if not bd_ht.empty:
                    st.dataframe(
                        bd_ht[["du_no", "ty_trong_pct", "dong_gop_hhi"]],
                        hide_index=True,
                        use_container_width=True,
                        height=250,
                    )

        # ═══════════ TOP MOVERS ════════════════════════════════════════════
        st.divider()
        with st.expander("🚀 Top movers (PGD có thay đổi lớn nhất)", expanded=False):
            top_n = st.slider(
                "Số PGD hiển thị",
                min_value=3,
                max_value=10,
                value=5,
                key=f"{key_prefix}top_movers_n",
            )
            df_top = _top_movers(df_ht, df_bl, COT_TEN_PGD, n=top_n)
            if not df_top.empty:
                st.dataframe(df_top, hide_index=True, use_container_width=True)
            else:
                st.info("Không đủ dữ liệu để hiển thị top movers.")
