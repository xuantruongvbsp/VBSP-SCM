"""So sánh số liệu giữa kỳ hiện tại và mốc 31/12 năm đã chọn."""
from __future__ import annotations

import os

import altair as alt
import pandas as pd
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from auth import la_phan_he_cn, normalize_role
from config import (
    COT_DU_NO_QH,
    COT_DU_NO_TH,
    COT_DVUT,
    COT_LAI_TON,
    COT_LAI_TON_QH,
    COT_MA_KH,
    COT_NGAY_SL,
    COT_NGAY_VAY,
    COT_NGUON_VON,
    COT_PHAN_LOAI,
    COT_SO_KU,
    COT_TEN_CT,
    COT_TEN_KH,
    COT_TEN_PGD,
    COT_TEN_XA,
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
from services.period_compare import (
    CHANGE_LABELS,
    CHANGE_TYPES,
    classify_changes,
    join_by_loan,
    par_breakdown,
    roll_cure_rate,
    vintage_nqh,
)
from utils import fmt_so, fmt_ty

COT_DU_NO_KHOANH = "Dư nợ khoanh"

_DIM_OPTIONS = [
    (COT_TEN_CT,     "Chương trình tín dụng"),
    (COT_NGUON_VON,  "Nguồn vốn"),
    (COT_TEN_XA,     "Xã"),
]


def _agg_mot_pgd(df: pd.DataFrame) -> dict:
    """Tổng hợp các chỉ tiêu chính cho 1 DataFrame (1 PGD hoặc toàn CN)."""
    if df is None or df.empty:
        return {
            "tong_du_no": 0, "du_no_th": 0, "du_no_qh": 0,
            "du_no_khoanh": 0, "so_ho": 0, "so_ku": 0, "gn_nam": 0,
            "tong_lai_ton": 0,
        }
    col_gn = next((c for c in HSTD_DS_CHO_VAY_NAM_ALIASES if c in df.columns), None)
    lai_th  = df[COT_LAI_TON].sum()    if COT_LAI_TON    in df.columns else 0
    lai_qh  = df[COT_LAI_TON_QH].sum() if COT_LAI_TON_QH in df.columns else 0
    return {
        "tong_du_no":    df[COT_TONG_DU_NO].sum()    if COT_TONG_DU_NO   in df.columns else 0,
        "du_no_th":      df[COT_DU_NO_TH].sum()      if COT_DU_NO_TH     in df.columns else 0,
        "du_no_qh":      df[COT_DU_NO_QH].sum()      if COT_DU_NO_QH     in df.columns else 0,
        "du_no_khoanh":  df[COT_DU_NO_KHOANH].sum()  if COT_DU_NO_KHOANH in df.columns else 0,
        "so_ho":         int(df[COT_MA_KH].nunique()) if COT_MA_KH        in df.columns else 0,
        "so_ku":         int(df[COT_SO_KU].nunique()) if COT_SO_KU        in df.columns else 0,
        "gn_nam":        df[col_gn].sum()             if col_gn                         else 0,
        "tong_lai_ton":  lai_th + lai_qh,
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


def _bang_par(df: pd.DataFrame, label: str) -> None:
    """Hiển thị PAR30/90/180 cho 1 DataFrame."""
    p = par_breakdown(df)
    c1, c2, c3 = st.columns(3)
    c1.metric(
        "PAR30",
        _fmt_pct_vn(p["par30_pct"] * 100),
        help=f"DN > 30 ngày QH: {fmt_ty(p['par30'])}",
    )
    c2.metric(
        "PAR90",
        _fmt_pct_vn(p["par90_pct"] * 100),
        help=f"DN > 90 ngày QH: {fmt_ty(p['par90'])}",
    )
    c3.metric(
        "PAR180",
        _fmt_pct_vn(p["par180_pct"] * 100),
        help=f"DN > 180 ngày QH: {fmt_ty(p['par180'])}",
    )


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


def _bang_explorer(df_joined: pd.DataFrame, chon_nam: str, key_prefix: str) -> None:
    """Bảng khế ước biến động — filter theo loại thay đổi."""
    if df_joined.empty:
        st.info("Không đủ dữ liệu để hiển thị biến động khế ước.")
        return

    df_cl = classify_changes(df_joined)
    if "_change_type" not in df_cl.columns:
        return

    all_label = f"Tất cả ({len(df_cl)})"
    type_counts = df_cl["_change_label"].value_counts()
    options = [all_label] + [
        f"{lbl} ({type_counts.get(lbl, 0)})"
        for lbl in CHANGE_LABELS
        if type_counts.get(lbl, 0) > 0
    ]
    choice = st.selectbox(
        "Lọc loại biến động",
        options,
        key=f"{key_prefix}explorer_filter",
    )

    if choice != all_label:
        lbl_filter = choice.rsplit(" (", 1)[0]
        df_show = df_cl[df_cl["_change_label"] == lbl_filter]
    else:
        df_show = df_cl

    col_map = {
        COT_SO_KU + "_curr": "Số KƯ",
        COT_MA_KH + "_curr": "Mã KH",
        COT_TEN_KH + "_curr": "Tên KH",
        COT_TEN_PGD + "_curr": "Tên PGD",
        "_change_label": "Loại biến động",
        COT_TONG_DU_NO + "_prev": f"DN mốc 31/12/{chon_nam}",
        COT_TONG_DU_NO + "_curr": "DN hiện tại",
        "_du_no_delta": "Δ DN",
        COT_DU_NO_QH + "_curr": "DN QH hiện tại",
    }
    available = {k: v for k, v in col_map.items() if k in df_show.columns}

    df_out = df_show[list(available.keys())].rename(columns=available).copy()

    for col_src, col_dst in available.items():
        if col_src in (
            COT_TONG_DU_NO + "_prev",
            COT_TONG_DU_NO + "_curr",
            COT_DU_NO_QH + "_curr",
        ):
            df_out[col_dst] = df_show[col_src].fillna(0).apply(fmt_ty)
        elif col_src == "_du_no_delta":
            df_out[col_dst] = df_show[col_src].apply(
                lambda x: ("+" if x >= 0 else "") + fmt_ty(x)
            )

    if "_du_no_delta" in df_show.columns:
        order = df_show["_du_no_delta"].abs().nlargest(500).index
        df_out = df_out.loc[df_out.index.intersection(order)].reindex(order).dropna(how="all")

    st.caption(f"Hiển thị {min(len(df_out), 500)} / {len(df_cl)} khế ước")
    st.dataframe(df_out.head(500), hide_index=True, use_container_width=True, height=420)


def _bang_vintage_nqh(df_ht: pd.DataFrame, df_bl: pd.DataFrame, chon_nam: str) -> None:
    """Bảng Vintage NQH: so sánh tỷ lệ NQH theo năm vay giữa mốc và hiện tại."""
    vt_ht = vintage_nqh(df_ht)
    vt_bl = vintage_nqh(df_bl)

    if vt_ht.empty and vt_bl.empty:
        st.info("Không có cột ngày vay để phân tích vintage.")
        return

    if vt_ht.empty:
        st.dataframe(vt_bl, hide_index=True, use_container_width=True)
        return
    if vt_bl.empty:
        st.dataframe(vt_ht, hide_index=True, use_container_width=True)
        return

    merged = vt_ht.merge(vt_bl, on="Năm vay", how="outer", suffixes=("_ht", "_bl")).fillna(0)
    merged = merged.sort_values("Năm vay")

    df_out = pd.DataFrame()
    df_out["Năm vay"] = merged["Năm vay"]
    df_out["DN mốc"] = merged["tong_du_no_bl"].apply(fmt_ty)
    df_out["NQH mốc"] = (merged["Tỷ lệ NQH_bl"] * 100).apply(_fmt_pct_vn)
    df_out["DN hiện tại"] = merged["tong_du_no_ht"].apply(fmt_ty)
    df_out["NQH HT"] = (merged["Tỷ lệ NQH_ht"] * 100).apply(_fmt_pct_vn)
    df_out["Δ NQH"] = ((merged["Tỷ lệ NQH_ht"] - merged["Tỷ lệ NQH_bl"]) * 100).apply(
        lambda x: ("+" if x >= 0 else "") + _fmt_pct_vn(abs(x)).replace("%", "") + "%"
    )

    st.dataframe(df_out, hide_index=True, use_container_width=True)


# ─── New visual helpers (port from PeriodOverview.tsx) ───────────────────────

def _chart_tang_truong(
    df_bl: pd.DataFrame,
    df_ht: pd.DataFrame,
    dim: str,
    label_bl: str,
    label_ht: str,
    key_prefix: str,
) -> None:
    """Grouped bar chart tăng trưởng dư nợ theo dimension, prev vs curr."""
    if COT_TONG_DU_NO not in df_bl.columns or COT_TONG_DU_NO not in df_ht.columns:
        st.info("Không đủ dữ liệu để vẽ biểu đồ.")
        return
    if dim not in df_bl.columns and dim not in df_ht.columns:
        st.info(f"Cột '{dim}' không có trong dữ liệu.")
        return

    def _group(df: pd.DataFrame) -> pd.DataFrame:
        if dim not in df.columns:
            return pd.DataFrame(columns=[dim, "dn"])
        g = df.groupby(dim, dropna=False)[COT_TONG_DU_NO].sum().reset_index()
        g.columns = [dim, "dn"]
        g[dim] = g[dim].fillna("—").astype(str)
        return g

    g_bl = _group(df_bl)
    g_ht = _group(df_ht)

    all_vals = sorted(
        set(g_bl[dim].tolist()) | set(g_ht[dim].tolist()),
    )
    focus = st.selectbox(
        "Tập trung vào",
        ["Tất cả"] + all_vals,
        key=f"{key_prefix}chart_focus_{dim}",
    )
    if focus != "Tất cả":
        g_bl = g_bl[g_bl[dim] == focus]
        g_ht = g_ht[g_ht[dim] == focus]

    g_bl = g_bl.assign(Ky=label_bl)
    g_ht = g_ht.assign(Ky=label_ht)
    combined = pd.concat([g_bl, g_ht], ignore_index=True)
    combined["dn_ty"] = combined["dn"] / 1e9

    if combined.empty or combined["dn_ty"].sum() == 0:
        st.info("Không có dữ liệu để hiển thị.")
        return

    chart = (
        alt.Chart(combined)
        .mark_bar()
        .encode(
            x=alt.X(f"{dim}:N", title=None, sort="-y",
                    axis=alt.Axis(labelAngle=-35, labelLimit=200)),
            y=alt.Y("dn_ty:Q", title="Dư nợ (tỷ đồng)"),
            color=alt.Color(
                "Ky:N",
                scale=alt.Scale(
                    domain=[label_bl, label_ht],
                    range=["#94a3b8", "#2563eb"],
                ),
                legend=alt.Legend(title="Kỳ"),
            ),
            xOffset="Ky:N",
            tooltip=[
                alt.Tooltip(f"{dim}:N", title=dim),
                alt.Tooltip("Ky:N", title="Kỳ"),
                alt.Tooltip("dn_ty:Q", title="Dư nợ (tỷ)", format=",.3f"),
            ],
        )
        .properties(height=340)
    )
    st.altair_chart(chart, use_container_width=True)


def _flow_diagram(
    prev_label: str,
    curr_label: str,
    prev_total: int,
    curr_total: int,
    left_label: str,
    left_count: int,
    mid_label: str,
    mid_count: int,
    right_label: str,
    right_count: int,
    badge: str = "",
) -> None:
    """Visual flow diagram dạng 3-box (port từ FlowDiagram.tsx)."""
    h1, h2, h3 = st.columns([2, 1, 2])
    with h1:
        st.markdown(
            f"<div style='text-align:center'>"
            f"<div style='font-size:10px;text-transform:uppercase;color:#64748b;letter-spacing:.05em'>{prev_label}</div>"
            f"<div style='font-size:1.6rem;font-weight:700;color:#0f172a'>{fmt_so(prev_total)}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with h2:
        st.markdown(
            "<div style='text-align:center;color:#94a3b8;font-size:1.2rem;padding-top:18px'>→</div>",
            unsafe_allow_html=True,
        )
    with h3:
        st.markdown(
            f"<div style='text-align:center'>"
            f"<div style='font-size:10px;text-transform:uppercase;color:#1d4ed8;letter-spacing:.05em'>{curr_label}</div>"
            f"<div style='font-size:1.6rem;font-weight:700;color:#1e3a8a'>{fmt_so(curr_total)}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='margin:8px 0'></div>", unsafe_allow_html=True)

    _CELL = (
        "<div style='border-radius:8px;padding:10px 6px;text-align:center;"
        "background:{bg};color:{fg};outline:1px solid {border};'>"
        "<div style='font-size:10px;font-weight:600;text-transform:uppercase;"
        "letter-spacing:.05em;opacity:.8'>{label}</div>"
        "<div style='font-size:1.3rem;font-weight:700'>{count}</div>"
        "{badge}"
        "</div>"
    )
    badge_html = (
        f"<div style='font-size:10px;font-weight:600;margin-top:2px'>{badge}</div>"
        if badge else ""
    )
    b1, b2, b3 = st.columns(3)
    b1.markdown(
        _CELL.format(bg="#f1f5f9", fg="#475569", border="#e2e8f0",
                     label=left_label, count=fmt_so(left_count), badge=""),
        unsafe_allow_html=True,
    )
    b2.markdown(
        _CELL.format(bg="#dbeafe", fg="#1e40af", border="#bfdbfe",
                     label=mid_label, count=fmt_so(mid_count), badge=badge_html),
        unsafe_allow_html=True,
    )
    b3.markdown(
        _CELL.format(bg="#d1fae5", fg="#065f46", border="#a7f3d0",
                     label=right_label, count=fmt_so(right_count), badge=""),
        unsafe_allow_html=True,
    )


def _quality_bars(
    snap_bl: dict,
    snap_ht: dict,
    label_bl: str,
    label_ht: str,
) -> None:
    """Stacked bar Trong hạn / Quá hạn / Khoanh cho 2 kỳ (port từ QualityStackedBars.tsx)."""
    max_total = max(snap_bl.get("total", 0), snap_ht.get("total", 0), 1)

    def _row(label: str, snap: dict) -> None:
        total = snap.get("total", 0)
        th = snap.get("trong_han", 0)
        qh = snap.get("qua_han", 0)
        kh = snap.get("khoanh", 0)

        width_pct = (total / max_total * 100) if max_total > 0 else 0
        th_pct = (th / total * 100) if total > 0 else 0
        qh_pct = (qh / total * 100) if total > 0 else 0
        kh_pct = (kh / total * 100) if total > 0 else 0

        st.markdown(
            f"<div style='margin-bottom:2px;display:flex;justify-content:space-between'>"
            f"<span style='font-size:12px;font-weight:600;color:#334155'>{label}</span>"
            f"<span style='font-size:11px;color:#64748b'>{fmt_ty(total)}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
        seg_th = (
            f"<div style='width:{th_pct:.2f}%;background:#34d399;height:100%' "
            f"title='Trong hạn {fmt_ty(th)}'></div>"
        ) if th_pct > 0 else ""
        seg_qh = (
            f"<div style='width:{qh_pct:.2f}%;background:#f43f5e;height:100%' "
            f"title='Quá hạn {fmt_ty(qh)}'></div>"
        ) if qh_pct > 0 else ""
        seg_kh = (
            f"<div style='width:{kh_pct:.2f}%;background:#fbbf24;height:100%' "
            f"title='Khoanh {fmt_ty(kh)}'></div>"
        ) if kh_pct > 0 else ""
        st.markdown(
            f"<div style='position:relative;height:28px;background:#f1f5f9;border-radius:6px;overflow:hidden'>"
            f"<div style='position:absolute;inset:0;display:flex;width:{width_pct:.2f}%'>"
            f"{seg_th}{seg_qh}{seg_kh}"
            f"</div></div>"
            f"<div style='display:grid;grid-template-columns:1fr 1fr 1fr;font-size:10px;color:#64748b;margin-top:3px'>"
            f"<span>Trong hạn: <strong style='color:#059669'>{_fmt_pct_vn(th_pct)}</strong></span>"
            f"<span style='text-align:center'>Quá hạn: <strong style='color:#e11d48'>{_fmt_pct_vn(qh_pct)}</strong></span>"
            f"<span style='text-align:right'>Khoanh: <strong style='color:#d97706'>{_fmt_pct_vn(kh_pct)}</strong></span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    _row(label_bl, snap_bl)
    st.markdown("<div style='margin:12px 0'></div>", unsafe_allow_html=True)
    _row(label_ht, snap_ht)


# ─────────────────────────────────────────────────────────────────────────────

def render(tab: DeltaGenerator = None, **kwargs) -> None:
    df       = kwargs.get("df")
    df_full  = kwargs.get("df_full", df)
    role_raw = str(kwargs.get("role", "user") or "user")
    role     = normalize_role(role_raw)
    pgd_user = kwargs.get("pgd_user")
    pgd_mode = kwargs.get("pgd_mode", False)

    ctx = tab if tab is not None else st.container()

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

        if pgd_mode and pgd_user and COT_TEN_PGD in df_bl_full.columns:
            df_bl = df_bl_full[df_bl_full[COT_TEN_PGD] == pgd_user].copy()
        else:
            df_bl = df_bl_full

        df_ht = df if pgd_mode else df_full
        if df_ht is None or df_ht.empty:
            st.warning("⚠️ Chưa có dữ liệu HSTD hiện tại.")
            return

        # ── Tổng hợp toàn bộ ─────────────────────────────────────────────
        agg_ht = _agg_mot_pgd(df_ht)
        agg_bl = _agg_mot_pgd(df_bl)

        df_joined = join_by_loan(df_bl, df_ht)

        ngay_sl = ""
        if "Ngày số liệu" in df_ht.columns:
            sl = df_ht["Ngày số liệu"].dropna()
            if len(sl):
                ngay_sl = str(sl.iloc[0])

        label_bl = f"31/12/{chon_nam}"
        label_ht = ngay_sl or "Hiện tại"

        st.caption(
            f"**Kỳ hiện tại:** {label_ht} &nbsp;|&nbsp; "
            f"**Mốc so sánh:** {label_bl}"
        )
        st.divider()

        # ═══════════ 8 KPI CARDS ═════════════════════════════════════════
        st.markdown("**📊 8 chỉ tiêu cốt lõi · Δ giữa hai kỳ**")

        tl_nqh_ht = _tl_nqh(agg_ht["du_no_qh"], agg_ht["tong_du_no"])
        tl_nqh_bl = _tl_nqh(agg_bl["du_no_qh"], agg_bl["tong_du_no"])
        muc_vay_bq_ht = agg_ht["tong_du_no"] / agg_ht["so_ho"] if agg_ht["so_ho"] > 0 else 0
        muc_vay_bq_bl = agg_bl["tong_du_no"] / agg_bl["so_ho"] if agg_bl["so_ho"] > 0 else 0

        # Hàng 1 — tăng trưởng
        r1c1, r1c2, r1c3, r1c4 = st.columns(4)
        r1c1.metric(
            "Tổng dư nợ",
            fmt_ty(agg_ht["tong_du_no"]),
            delta=_delta_str(agg_ht["tong_du_no"], agg_bl["tong_du_no"]),
            help=f"Mốc {label_bl}: {fmt_ty(agg_bl['tong_du_no'])}",
        )
        r1c2.metric(
            "Số khế ước",
            fmt_so(agg_ht["so_ku"]),
            delta=_delta_str(agg_ht["so_ku"], agg_bl["so_ku"], unit="so"),
            help=f"Mốc {label_bl}: {fmt_so(agg_bl['so_ku'])}",
        )
        r1c3.metric(
            "Số hộ vay",
            fmt_so(agg_ht["so_ho"]),
            delta=_delta_str(agg_ht["so_ho"], agg_bl["so_ho"], unit="so"),
            help=f"Mốc {label_bl}: {fmt_so(agg_bl['so_ho'])}",
        )
        r1c4.metric(
            "Mức vay BQ/KH",
            fmt_ty(muc_vay_bq_ht),
            delta=_delta_str(muc_vay_bq_ht, muc_vay_bq_bl),
            help=f"Mốc {label_bl}: {fmt_ty(muc_vay_bq_bl)}",
        )

        # Hàng 2 — rủi ro
        r2c1, r2c2, r2c3, r2c4 = st.columns(4)
        r2c1.metric(
            "Tỷ lệ NQH",
            _fmt_pct_vn(tl_nqh_ht),
            delta=_fmt_pct_vn(tl_nqh_ht - tl_nqh_bl),
            delta_color="inverse",
            help=f"Mốc {label_bl}: {_fmt_pct_vn(tl_nqh_bl)}",
        )
        r2c2.metric(
            "Dư nợ quá hạn",
            fmt_ty(agg_ht["du_no_qh"]),
            delta=_delta_str(agg_ht["du_no_qh"], agg_bl["du_no_qh"]),
            delta_color="inverse",
            help=f"Mốc {label_bl}: {fmt_ty(agg_bl['du_no_qh'])}",
        )
        r2c3.metric(
            "Dư nợ khoanh",
            fmt_ty(agg_ht["du_no_khoanh"]),
            delta=_delta_str(agg_ht["du_no_khoanh"], agg_bl["du_no_khoanh"]),
            delta_color="inverse",
            help=f"Mốc {label_bl}: {fmt_ty(agg_bl['du_no_khoanh'])}",
        )
        r2c4.metric(
            "Lãi tồn TH",
            fmt_ty(agg_ht["lai_ton"]),
            delta=_delta_str(agg_ht["lai_ton"], agg_bl["lai_ton"]),
            delta_color="inverse",
            help=f"Mốc {label_bl}: {fmt_ty(agg_bl['lai_ton'])}",
        )

        st.divider()

        # ── Chi tiết chỉ tiêu ─────────────────────────────────────────────
        with st.expander("📋 Chi tiết chỉ tiêu", expanded=True):
            rows = [
                ("Tổng dư nợ",         agg_bl["tong_du_no"],   agg_ht["tong_du_no"],   "ty"),
                ("  Dư nợ trong hạn",  agg_bl["du_no_th"],     agg_ht["du_no_th"],     "ty"),
                ("  Dư nợ quá hạn",    agg_bl["du_no_qh"],     agg_ht["du_no_qh"],     "ty"),
                ("  Dư nợ khoanh",     agg_bl["du_no_khoanh"], agg_ht["du_no_khoanh"], "ty"),
                ("  Lãi tồn TH",       agg_bl["lai_ton"],      agg_ht["lai_ton"],      "ty"),
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
                    f"Mốc {label_bl}": fmt_ty(bl_val) if unit == "ty" else fmt_so(int(bl_val)),
                    "Hiện tại":        fmt_ty(ht_val) if unit == "ty" else fmt_so(int(ht_val)),
                    "Chênh lệch":      f"{sign}{fmt_ty(delta)}" if unit == "ty" else f"{sign}{fmt_so(int(delta))}",
                    "% thay đổi":      f"{sign}{pct:.2f}".replace(".", ",") + "%",
                })
            df_ct = pd.DataFrame(data_ct)
            st.dataframe(df_ct, hide_index=True, use_container_width=True)

        # ═══════════ TĂNG TRƯỞNG DƯ NỢ ══════════════════════════════════
        st.divider()
        st.markdown("**📊 Tăng trưởng dư nợ**")

        dim_labels = {col: lbl for col, lbl in _DIM_OPTIONS}
        dim_sel = st.radio(
            "Phân tích theo",
            options=[col for col, _ in _DIM_OPTIONS],
            format_func=lambda x: dim_labels[x],
            horizontal=True,
            key=f"{key_prefix}chart_dim",
        )
        _chart_tang_truong(df_bl, df_ht, dim_sel, label_bl, label_ht, key_prefix)

        # ═══════════ VÒNG ĐỜI KHẾ ƯỚC / KHÁCH HÀNG ═════════════════════
        st.divider()
        st.markdown("**🔄 Vòng đời danh mục**")

        # Tính loan lifecycle
        prev_total_loans = agg_bl["so_ku"]
        curr_total_loans = agg_ht["so_ku"]
        prev_col = COT_SO_KU + "_prev"
        curr_col = COT_SO_KU + "_curr"
        if (
            not df_joined.empty
            and prev_col in df_joined.columns
            and curr_col in df_joined.columns
        ):
            retained_loans = int(
                df_joined[[prev_col, curr_col]].notna().all(axis=1).sum()
            )
        else:
            retained_loans = min(prev_total_loans, curr_total_loans)
        closed_loans = max(0, prev_total_loans - retained_loans)
        new_loans    = max(0, curr_total_loans - retained_loans)

        # Tính customer lifecycle
        ma_kh_bl = (
            set(df_bl[COT_MA_KH].astype(str).str.strip())
            if COT_MA_KH in df_bl.columns else set()
        )
        ma_kh_ht = (
            set(df_ht[COT_MA_KH].astype(str).str.strip())
            if COT_MA_KH in df_ht.columns else set()
        )
        prev_total_cust = len(ma_kh_bl)
        curr_total_cust = len(ma_kh_ht)
        retained_cust   = len(ma_kh_bl & ma_kh_ht)
        churned_cust    = len(ma_kh_bl - ma_kh_ht)
        new_cust        = len(ma_kh_ht - ma_kh_bl)

        lc1, lc2 = st.columns(2)
        with lc1:
            st.markdown("**Khế ước**")
            _flow_diagram(
                prev_label=f"KƯ {label_bl}",
                curr_label=f"KƯ {label_ht}",
                prev_total=prev_total_loans,
                curr_total=curr_total_loans,
                left_label="Đã tất toán",
                left_count=closed_loans,
                mid_label="Duy trì",
                mid_count=retained_loans,
                right_label="Khế ước mới",
                right_count=new_loans,
            )
        with lc2:
            st.markdown("**Khách hàng**")
            _flow_diagram(
                prev_label=f"KH {label_bl}",
                curr_label=f"KH {label_ht}",
                prev_total=prev_total_cust,
                curr_total=curr_total_cust,
                left_label="Đã rời danh mục",
                left_count=churned_cust,
                mid_label="Còn vay",
                mid_count=retained_cust,
                right_label="Khách hàng mới",
                right_count=new_cust,
            )

        # ═══════════ CHẤT LƯỢNG DƯ NỢ ════════════════════════════════════
        st.divider()
        st.markdown("**📐 Cơ cấu chất lượng dư nợ**")

        def _snap(agg: dict) -> dict:
            total = agg["tong_du_no"]
            th = agg["du_no_th"]
            qh = agg["du_no_qh"]
            kh = agg["du_no_khoanh"]
            if th == 0 and total > 0:
                th = max(0.0, total - qh - kh)
            return {"trong_han": th, "qua_han": qh, "khoanh": kh, "total": total}

        _quality_bars(
            snap_bl=_snap(agg_bl),
            snap_ht=_snap(agg_ht),
            label_bl=f"Kỳ trước · {label_bl}",
            label_ht=f"Kỳ sau · {label_ht}",
        )

        # ═══════════ BẢNG THEO PGD (chỉ CN role) ═════════════════════════
        if la_phan_he_cn(role) and not pgd_mode:
            st.divider()
            st.markdown("**🗺️ Chi tiết theo PGD**")

            df_pgd_ht = _agg_theo_pgd(df_full)
            df_pgd_bl = _agg_theo_pgd(df_bl_full)

            if df_pgd_ht.empty or df_pgd_bl.empty:
                st.info("Không đủ dữ liệu để so sánh theo PGD.")
                return

            df_merge = df_pgd_ht.merge(
                df_pgd_bl,
                on=COT_TEN_PGD,
                how="outer",
                suffixes=("_ht", "_bl"),
            ).fillna(0)

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

            df_out = pd.DataFrame()
            df_out["Tên PGD"]              = df_merge[COT_TEN_PGD]
            df_out[f"DN mốc {label_bl}"]   = df_merge["tong_du_no_bl"].apply(fmt_ty)
            df_out["DN hiện tại"]          = df_merge["tong_du_no_ht"].apply(fmt_ty)
            df_out["±DN"]                  = df_merge["Δ Dư nợ"].apply(
                lambda x: ("+" if x >= 0 else "") + fmt_ty(x)
            )
            df_out["±DN%"] = df_merge["Δ DN %"].apply(
                lambda x: ("+" if x >= 0 else "") + f"{x:.2f}".replace(".", ",") + "%"
            )
            df_out[f"Hộ mốc {label_bl}"]   = df_merge["so_ho_bl"].apply(lambda x: fmt_so(int(x)))
            df_out["Hộ HT"]               = df_merge["so_ho_ht"].apply(lambda x: fmt_so(int(x)))
            df_out["±Hộ"]                  = df_merge["Δ Hộ"].apply(
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
            st.markdown("**Phân tích thay đổi nhóm khách hàng giữa hai kỳ:**")
            df_lifecycle = _phan_loai_khach_hang(df_bl, df_ht)
            if not df_lifecycle.empty:
                st.dataframe(df_lifecycle, hide_index=True, use_container_width=True)
            else:
                st.info("Không đủ dữ liệu khách hàng để phân loại.")

        # ═══════════ PHÂN TÍCH PAR ═════════════════════════════════════════
        st.divider()
        with st.expander("🎯 Phân tích PAR (Portfolio at Risk)", expanded=False):
            st.markdown(
                "**PAR30/PAR90/PAR180** — tỷ lệ dư nợ có ngày đáo hạn > 30/90/180 ngày"
            )
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**Mốc {label_bl}**")
                _bang_par(df_bl, f"Mốc {label_bl}")
            with c2:
                st.markdown("**Hiện tại**")
                _bang_par(df_ht, "Hiện tại")

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

        # ═══════════ BIẾN ĐỘNG KHẾƯỚC (EXPLORER) ════════════════════════
        st.divider()
        with st.expander("🔍 Biến động khế ước chi tiết", expanded=False):
            st.markdown(
                "Phân loại **8 loại biến động** cấp độ khế ước giữa mốc và hiện tại. "
                "Sắp xếp theo |Δ dư nợ| giảm dần."
            )
            _bang_explorer(df_joined, chon_nam, key_prefix)

        # ═══════════ ROLL RATE / CURE RATE (từ join trực tiếp) ══════════
        st.divider()
        with st.expander("📊 Roll rate / Cure rate", expanded=False):
            rc = roll_cure_rate(df_joined)
            st.markdown(
                "**Roll rate** = tỷ lệ dư nợ Trong hạn ở kỳ trước chuyển sang Quá hạn kỳ này.  \n"
                "**Cure rate** = tỷ lệ dư nợ Quá hạn ở kỳ trước phục hồi về Trong hạn kỳ này."
            )
            r1, r2 = st.columns(2)
            r1.metric(
                "Roll rate",
                _fmt_pct_vn(rc["roll_rate"] * 100),
                help=f"DN TH kỳ trước: {fmt_ty(rc['base_th_prev'])} | Số KƯ roll: {fmt_so(rc['roll_count'])}",
                delta_color="inverse",
            )
            r2.metric(
                "Cure rate",
                _fmt_pct_vn(rc["cure_rate"] * 100),
                help=f"DN QH kỳ trước: {fmt_ty(rc['base_qh_prev'])} | Số KƯ cure: {fmt_so(rc['cure_count'])}",
            )

        # ═══════════ VINTAGE NQH ════════════════════════════════════════
        st.divider()
        with st.expander("📅 Vintage NQH (theo năm vay)", expanded=False):
            st.markdown(
                "Tỷ lệ NQH phân tích theo **năm phát sinh khoản vay** — "
                "cho thấy nhóm vintage nào có rủi ro cao nhất."
            )
            _bang_vintage_nqh(df_ht, df_bl, chon_nam)
