"""So sánh nhiều kỳ — 4 tabs ngang: HSTD / NQ11 / GQVL / CDTOTKVV.

Layout:
  - Bộ lọc trên đầu: multiselect kỳ (tối đa 6) + lọc PGD
  - 4 tabs ngang, mỗi tab hiển thị đầy đủ không cần mở expander
"""
from __future__ import annotations

import streamlit as st
import pandas as pd
from streamlit.delta_generator import DeltaGenerator

import plotly.graph_objects as go

import db
from auth import normalize_role, la_phan_he_pgd, la_phan_he_cn
from utils import fmt_ty, fmt_so, lazy_tabs
from tabs.base_tab import TabContext
from state_manager import SCMStateManager
from snapshot_service import (
    compare_snapshot_2_ky, danh_sach_ky, doc_snapshot, doc_snapshot_multi,
    doc_snapshot_theo_ct, export_snapshot_excel, ky_baseline,
    danh_sach_ky_nq11, doc_nq11_snapshot,
    danh_sach_ky_gqvl, doc_gqvl_snapshot,
    danh_sach_ky_cdtotkvv, doc_cdtotkvv_snapshot,
)
from tabs.tab_so_sanh_ky._common import (
    delta_str, pct_change_str, fmt_pct_vn, tl_nqh,
    render_kpi_row, render_quality_bars_2_ky,
    render_hbar_chart, render_trend_chart,
    render_multi_period_table, render_ct_breakdown_table,
    inject_qb_css,
)
from tabs.tab_so_sanh_ky._export import render_export_ui, build_excel_sheets_pgd
from config import CHUONG_TRINH_KHTD as _CT_CFG


# ─── HELPERS ────────────────────────────────────────────────────────────────

def _agg(df: pd.DataFrame) -> dict:
    zero = {k: 0.0 for k in
            ["tong_du_no", "du_no_th", "du_no_qh", "du_no_khoanh", "so_ho", "so_ku", "gn_nam"]}
    if df is None or df.empty:
        return zero
    return {
        "tong_du_no":   float(df["tong_du_no"].sum()),
        "du_no_th":     float(df["du_no_th"].sum()),
        "du_no_qh":     float(df["du_no_qh"].sum()),
        "du_no_khoanh": float(df["du_no_khoanh"].sum()),
        "so_ho":        float(df["so_ho"].sum()),
        "so_ku":        float(df["so_ku"].sum()),
        "gn_nam":       float(df["gn_nam"].sum()),
    }


def _dn_bq_ho(agg: dict) -> float:
    return agg["tong_du_no"] / agg["so_ho"] if agg["so_ho"] > 0 else 0.0


def _gn_bq_ho(agg: dict) -> float:
    return agg["gn_nam"] / agg["so_ho"] if agg["so_ho"] > 0 else 0.0


def _tl_no_xau(agg: dict) -> float:
    dn = agg["tong_du_no"]
    return (agg["du_no_qh"] + agg["du_no_khoanh"]) / dn * 100 if dn > 0 else 0.0


# ─── BỘ LỌC ─────────────────────────────────────────────────────────────────

def _render_bo_loc(
    ds_ky: list[str],
    pgd_mode: bool,
    pgd_user: str | None,
    pgd_data_list: list[str],
) -> tuple[list[str], str | None]:
    """Render bộ lọc kỳ + PGD, trả về (ky_list_chon, pgd_filter)."""
    inject_qb_css()
    col_ky, col_pgd = st.columns([3, 2])

    with col_ky:
        _bl = ky_baseline(ds_ky, ds_ky[0]) if ds_ky else None
        _seen: set[str] = set()
        _default: list[str] = []
        for _k in ([ds_ky[0]] if ds_ky else []) + ([_bl] if _bl else []) + ds_ky[1:]:
            if _k and _k not in _seen and len(_default) < 3:
                _default.append(_k)
                _seen.add(_k)
        default_ky = sorted(_default, reverse=True)
        ky_chon = st.multiselect(
            "📅 Chọn kỳ so sánh (tối đa 6)",
            options=ds_ky,
            default=default_ky,
            max_selections=6,
            key="mnk_ky_multi",
            help="Chọn ít nhất 2 kỳ. Thứ tự hiển thị: mới trước.",
        )

    pgd_filter = None
    if not pgd_mode and pgd_data_list:
        with col_pgd:
            state = SCMStateManager()
            opts = ["🏢 Tất cả Chi nhánh"] + pgd_data_list
            desired = state.filter_pgd or "🏢 Tất cả Chi nhánh"
            if "mnk_pgd_filter" not in st.session_state:
                st.session_state["mnk_pgd_filter"] = desired if desired in opts else "🏢 Tất cả Chi nhánh"
            elif st.session_state.get("mnk_pgd_filter") not in opts:
                st.session_state["mnk_pgd_filter"] = "🏢 Tất cả Chi nhánh"
            pgd_filter = st.selectbox("📍 Lọc PGD", opts, key="mnk_pgd_filter")
            if pgd_filter == "🏢 Tất cả Chi nhánh":
                state.filter_pgd = None
                pgd_filter = None
            else:
                state.filter_pgd = pgd_filter

    if len(ky_chon) < 2:
        st.warning("⚠️ Vui lòng chọn ít nhất **2 kỳ** để so sánh.")
        return [], pgd_filter

    # Sắp xếp kỳ theo thứ tự tăng dần (cũ → mới) cho biểu đồ xu hướng
    ky_sorted = sorted(ky_chon)
    return ky_sorted, pgd_filter


# ─── TAB HSTD ───────────────────────────────────────────────────────────────

def _render_hstd_tab(
    ky_list: list[str],
    pgd_mode: bool,
    pgd_user: str | None,
    pgd_filter: str | None,
    username: str,
) -> None:
    if not ky_list:
        return

    ky_dau = ky_list[0]
    ky_cuoi = ky_list[-1]

    # Tải dữ liệu kỳ đầu và cuối để so sánh
    df_dau_raw = doc_snapshot(ky_dau)
    df_cuoi_raw = doc_snapshot(ky_cuoi)

    if df_dau_raw.empty or df_cuoi_raw.empty:
        st.warning("⚠️ Một hoặc nhiều kỳ chưa có dữ liệu snapshot.")
        return

    # Áp dụng lọc PGD
    def _loc(df: pd.DataFrame) -> pd.DataFrame:
        if pgd_mode and pgd_user:
            return df[df["ten_pgd"] == pgd_user].reset_index(drop=True)
        if pgd_filter:
            return df[df["ten_pgd"] == pgd_filter].reset_index(drop=True)
        return df

    df_dau = _loc(df_dau_raw)
    df_cuoi = _loc(df_cuoi_raw)
    if df_dau.empty or df_cuoi.empty:
        st.warning("⚠️ Không có dữ liệu cho bộ lọc đã chọn.")
        return

    agg_dau = _agg(df_dau)
    agg_cuoi = _agg(df_cuoi)
    tl_dau = tl_nqh(agg_dau["du_no_qh"], agg_dau["tong_du_no"])
    tl_cuoi = tl_nqh(agg_cuoi["du_no_qh"], agg_cuoi["tong_du_no"])
    no_xau_dau = _tl_no_xau(agg_dau)
    no_xau_cuoi = _tl_no_xau(agg_cuoi)

    ten_hien_thi = pgd_filter or (pgd_user if pgd_mode else "Toàn Chi nhánh")
    st.caption(f"So sánh **{ky_dau}** → **{ky_cuoi}** · {ten_hien_thi} · {len(ky_list)} kỳ")

    # ── Section A: KPI row ──
    st.markdown("**📊 Tổng quan** *(kỳ đầu → kỳ cuối)*")
    render_kpi_row([
        {"label": "💰 Tổng dư nợ (triệu đồng)", "value": fmt_ty(agg_cuoi["tong_du_no"]),
         "delta": agg_cuoi["tong_du_no"] - agg_dau["tong_du_no"], "unit": "tien",
         "help": f"Kỳ {ky_dau}: {fmt_ty(agg_dau['tong_du_no'])}"},
        {"label": "⚠️ Dư nợ quá hạn (triệu đồng)", "value": fmt_ty(agg_cuoi["du_no_qh"]),
         "delta": agg_cuoi["du_no_qh"] - agg_dau["du_no_qh"], "unit": "tien", "inverse": True,
         "help": f"Kỳ {ky_dau}: {fmt_ty(agg_dau['du_no_qh'])}"},
        {"label": "📊 Tỷ lệ NQH", "value": fmt_pct_vn(tl_cuoi),
         "delta": tl_cuoi - tl_dau, "unit": "pct", "inverse": True,
         "help": f"Kỳ {ky_dau}: {fmt_pct_vn(tl_dau)}"},
        {"label": "🔴 Tỷ lệ nợ xấu (QH+Khoanh)", "value": fmt_pct_vn(no_xau_cuoi),
         "delta": no_xau_cuoi - no_xau_dau, "unit": "pct", "inverse": True,
         "help": f"Kỳ {ky_dau}: {fmt_pct_vn(no_xau_dau)}"},
    ])
    render_kpi_row([
        {"label": "👥 Số hộ vay", "value": fmt_so(int(agg_cuoi["so_ho"])),
         "delta": agg_cuoi["so_ho"] - agg_dau["so_ho"], "unit": "so",
         "help": f"Kỳ {ky_dau}: {fmt_so(int(agg_dau['so_ho']))}"},
        {"label": "📋 Số khế ước", "value": fmt_so(int(agg_cuoi["so_ku"])),
         "delta": agg_cuoi["so_ku"] - agg_dau["so_ku"], "unit": "so",
         "help": f"Kỳ {ky_dau}: {fmt_so(int(agg_dau['so_ku']))}"},
        {"label": "📐 DN bình quân/hộ (triệu)", "value": fmt_ty(_dn_bq_ho(agg_cuoi)),
         "delta": _dn_bq_ho(agg_cuoi) - _dn_bq_ho(agg_dau), "unit": "tien",
         "help": f"Kỳ {ky_dau}: {fmt_ty(_dn_bq_ho(agg_dau))} triệu/hộ"},
        {"label": "💵 Giải ngân BQ/hộ (triệu)", "value": fmt_ty(_gn_bq_ho(agg_cuoi)),
         "delta": _gn_bq_ho(agg_cuoi) - _gn_bq_ho(agg_dau), "unit": "tien",
         "help": f"Kỳ {ky_dau}: {fmt_ty(_gn_bq_ho(agg_dau))} triệu/hộ"},
    ])

    st.divider()

    # ── Section B: Xu hướng nhiều kỳ ──
    st.markdown("**📈 Xu hướng nhiều kỳ**")

    # Tải dữ liệu nhiều kỳ — dùng tuple để cache hoạt động đúng
    if not pgd_mode and not pgd_filter:
        df_multi = doc_snapshot_multi(tuple(ky_list))
    else:
        # PGD mode: tổng hợp từ từng kỳ
        rows = []
        for ky in ky_list:
            df_k = doc_snapshot(ky)
            df_k = _loc(df_k)
            if not df_k.empty:
                a = _agg(df_k)
                a["ky"] = ky
                rows.append(a)
        df_multi = pd.DataFrame(rows) if rows else pd.DataFrame()

    metric_opt = st.selectbox(
        "Chỉ tiêu xu hướng",
        ["Tổng dư nợ", "Dư nợ trong hạn / Quá hạn", "Tỷ lệ NQH%", "Số hộ vay", "Giải ngân"],
        key="mnk_trend_metric",
        label_visibility="collapsed",
    )
    if not df_multi.empty:
        if metric_opt == "Tổng dư nợ":
            render_trend_chart(df_multi, "tong_du_no",
                               title="Xu hướng Tổng dư nợ (triệu đồng)", key="mnk_trend_dn")
        elif metric_opt == "Dư nợ trong hạn / Quá hạn":
            render_trend_chart(df_multi, ["du_no_th", "du_no_qh"],
                               title="DN trong hạn vs Quá hạn (triệu đồng)", key="mnk_trend_th_qh")
        elif metric_opt == "Tỷ lệ NQH%":
            if "tong_du_no" in df_multi.columns and "du_no_qh" in df_multi.columns:
                df_multi = df_multi.copy()
                df_multi["tl_nqh_pct"] = (
                    df_multi["du_no_qh"] / df_multi["tong_du_no"].replace(0, float("nan")) * 100
                ).fillna(0)
                render_trend_chart(df_multi, "tl_nqh_pct",
                                   title="Xu hướng Tỷ lệ NQH (%)", y_label="%", key="mnk_trend_nqh")
        elif metric_opt == "Số hộ vay":
            render_trend_chart(df_multi, "so_ho",
                               title="Xu hướng Số hộ vay", y_label="Hộ", key="mnk_trend_ho")
        else:
            render_trend_chart(df_multi, "gn_nam",
                               title="Xu hướng Giải ngân (triệu đồng)", key="mnk_trend_gn")

    st.divider()

    # ── Section C: Chất lượng dư nợ 2 kỳ đầu-cuối ──
    st.markdown("**⚡ Chất lượng dư nợ** *(kỳ đầu vs kỳ cuối)*")
    render_quality_bars_2_ky(
        f"Kỳ {ky_dau}", agg_dau["tong_du_no"], agg_dau["du_no_th"],
        agg_dau["du_no_qh"], agg_dau["du_no_khoanh"],
        f"Kỳ {ky_cuoi}", agg_cuoi["tong_du_no"], agg_cuoi["du_no_th"],
        agg_cuoi["du_no_qh"], agg_cuoi["du_no_khoanh"],
    )

    st.divider()

    # ── Section D: Bảng so sánh nhiều kỳ ──
    st.markdown("**📋 Bảng so sánh chi tiết**")

    # Tập hợp agg theo từng kỳ
    agg_list = []
    for ky in ky_list:
        dfk = doc_snapshot(ky)
        dfk = _loc(dfk)
        agg_list.append(_agg(dfk))

    rows_table = [
        ("Tổng dư nợ (triệu đồng)",
         [a["tong_du_no"] for a in agg_list], False, "tien"),
        ("Dư nợ trong hạn (triệu đồng)",
         [a["du_no_th"] for a in agg_list], False, "tien"),
        ("Dư nợ quá hạn (triệu đồng)",
         [a["du_no_qh"] for a in agg_list], True, "tien"),
        ("Dư nợ khoanh (triệu đồng)",
         [a["du_no_khoanh"] for a in agg_list], True, "tien"),
        ("Tỷ lệ NQH (%)",
         [tl_nqh(a["du_no_qh"], a["tong_du_no"]) for a in agg_list], True, "pct"),
        ("Tỷ lệ nợ xấu QH+Khoanh (%)",
         [_tl_no_xau(a) for a in agg_list], True, "pct"),
        ("Số hộ vay",
         [a["so_ho"] for a in agg_list], False, "so"),
        ("Số khế ước",
         [a["so_ku"] for a in agg_list], False, "so"),
        ("DN bình quân/hộ (triệu)",
         [_dn_bq_ho(a) for a in agg_list], False, "tien"),
        ("Giải ngân trong năm (triệu đồng)",
         [a["gn_nam"] for a in agg_list], False, "tien"),
        ("Giải ngân BQ/hộ (triệu)",
         [_gn_bq_ho(a) for a in agg_list], False, "tien"),
    ]
    render_multi_period_table(rows_table, ky_list)

    # ── Section E: Phân tích chiều (chỉ toàn CN) ──
    is_toan_cn = not pgd_mode and not pgd_filter
    if is_toan_cn:
        st.divider()
        st.markdown("**🔍 Phân tích chiều**")
        chieu = st.radio(
            "Chiều phân tích",
            ["🏢 Theo PGD", "📑 Theo Chương trình tín dụng"],
            horizontal=True,
            key="mnk_chieu",
            label_visibility="collapsed",
        )

        if chieu == "🏢 Theo PGD":
            # Bảng biến động PGD (kỳ đầu vs kỳ cuối)
            _render_bang_pgd_2ky(df_dau_raw, df_cuoi_raw, ky_dau, ky_cuoi)
            st.divider()
            # Bar chart biến động dư nợ
            m1 = df_dau_raw[["ten_pgd", "tong_du_no"]].rename(columns={"tong_du_no": "dn1"})
            m2 = df_cuoi_raw[["ten_pgd", "tong_du_no"]].rename(columns={"tong_du_no": "dn2"})
            jn = pd.merge(m1, m2, on="ten_pgd", how="outer").fillna(0)
            jn["delta"] = jn["dn2"] - jn["dn1"]
            jn = jn[~jn["ten_pgd"].astype(str).str.startswith("__")].sort_values("delta")
            if not jn.empty:
                render_hbar_chart(
                    labels=jn["ten_pgd"].astype(str).tolist(),
                    values=jn["delta"].tolist(),
                    title=f"Biến động dư nợ theo PGD: {ky_dau} → {ky_cuoi}",
                    key="mnk_hbar_pgd",
                )
        else:
            # Bảng theo chương trình tín dụng
            df_ct = doc_snapshot_theo_ct(ky_cuoi)
            if df_ct.empty:
                st.info("ℹ️ Chưa có dữ liệu chi tiết theo chương trình cho kỳ này.")
            else:
                # Xây dựng dict {ma_ct_int: ten_ct} từ config
                ct_name_map: dict = {}
                for _mk, _ma, _ten, _nv, _ in _CT_CFG:
                    if _ma not in ct_name_map:
                        ct_name_map[_ma] = _ten
                render_ct_breakdown_table(df_ct, ky_cuoi, ct_name_map)
                st.divider()
                # Bar chart top chương trình
                top_ct = df_ct.head(10)
                if not top_ct.empty:
                    labels_ct = [
                        ct_name_map.get(int(r["ma_ct"]), f"CT {r['ma_ct']}")[:25]
                        for _, r in top_ct.iterrows()
                    ]
                    values_ct = top_ct["tong_du_no"].tolist()
                    fig_ct = go.Figure(go.Bar(
                        y=labels_ct, x=values_ct, orientation="h",
                        marker_color="var(--blue, #2563eb)",
                        text=[fmt_ty(v) for v in values_ct],
                        textposition="outside",
                    ))
                    fig_ct.update_layout(
                        title=dict(text=f"Top 10 CT dư nợ kỳ {ky_cuoi}", font_size=13),
                        height=max(260, len(labels_ct) * 30 + 60),
                        margin=dict(t=36, b=10, l=10, r=80),
                        xaxis_title="Triệu đồng",
                        showlegend=False,
                    )
                    st.plotly_chart(fig_ct, use_container_width=True, key="mnk_ct_bar")

    # ── Section F: Xuất Excel ──
    st.divider()
    _render_export_hstd(agg_dau, agg_cuoi, ky_dau, ky_cuoi, df_dau_raw, df_cuoi_raw, username, pgd_mode)
    if not pgd_mode:
        raw_key = f"_mnk_snapshot_raw_{'_'.join(ky_list)}"
        if raw_key not in st.session_state:
            st.session_state[raw_key] = export_snapshot_excel(ky_list, "hstd")
        if st.download_button(
            "📦 Xuất Excel snapshot gốc các kỳ đã chọn",
            data=st.session_state[raw_key],
            file_name=f"snapshot_hstd_{ky_dau}_den_{ky_cuoi}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="mnk_dl_snapshot_raw",
            use_container_width=True,
        ):
            db.ghi_audit(username, "xuat_bieu_cn", f"Xuất Excel snapshot HSTD gốc: {', '.join(ky_list)}")


def _render_bang_pgd_2ky(df1: pd.DataFrame, df2: pd.DataFrame,
                          ky1: str, ky2: str) -> None:
    """Bảng biến động PGD kỳ đầu vs kỳ cuối (dùng lại logic từ render_2_ky)."""
    comp = compare_snapshot_2_ky(ky1, ky2)
    if comp.empty:
        return
    jn = comp.rename(columns={
        "tong_du_no_prev": "dn1",
        "tong_du_no": "dn2",
        "du_no_qh_prev": "nqh1",
        "du_no_qh": "nqh2",
        "so_ho_prev": "ho1",
        "so_ho": "ho2",
        "tong_du_no_delta": "delta_dn",
        "du_no_qh_delta": "delta_nqh",
        "so_ho_delta": "delta_ho",
    })
    jn = jn[~jn["ten_pgd"].astype(str).str.startswith("__")].copy()
    jn["tl_nqh1"] = (jn["nqh1"] / jn["dn1"].replace(0, float("nan")) * 100).fillna(0.0)
    jn["tl_nqh2"] = (jn["nqh2"] / jn["dn2"].replace(0, float("nan")) * 100).fillna(0.0)

    tong = {
        "ten_pgd": "⬛ Tổng Chi nhánh",
        "dn1": jn["dn1"].sum(), "dn2": jn["dn2"].sum(),
        "delta_dn": jn["delta_dn"].sum(),
        "nqh1": jn["nqh1"].sum(), "nqh2": jn["nqh2"].sum(),
        "delta_nqh": jn["delta_nqh"].sum(),
        "ho1": jn["ho1"].sum(), "ho2": jn["ho2"].sum(),
        "delta_ho": jn["delta_ho"].sum(),
        "tl_nqh1": jn["nqh1"].sum() / jn["dn1"].sum() * 100 if jn["dn1"].sum() else 0,
        "tl_nqh2": jn["nqh2"].sum() / jn["dn2"].sum() * 100 if jn["dn2"].sum() else 0,
    }
    jn = pd.concat([jn.sort_values("delta_dn", ascending=False),
                    pd.DataFrame([tong])], ignore_index=True)
    # Lọc bỏ dòng __CN__ và __PGD__
    jn = jn[~jn["ten_pgd"].astype(str).str.startswith("__")]

    def _row_html(r: pd.Series) -> str:
        is_tong = str(r["ten_pgd"]).startswith("⬛")
        bold = "font-weight:700;" if is_tong else ""
        bg = "var(--surface-hi,rgba(46,125,50,0.08))" if is_tong else ""
        cl_dn = "class='delta-pos'" if r["delta_dn"] >= 0 else "class='delta-neg'"
        cl_nqh = "class='delta-pos'" if r["tl_nqh2"] - r["tl_nqh1"] <= 0 else "class='delta-neg'"
        return (
            f"<tr style='border-bottom:1px solid var(--border,#e5e7eb);background:{bg}'>"
            f"<td style='padding:7px 10px;{bold}'>{r['ten_pgd']}</td>"
            f"<td style='padding:7px 10px;text-align:right'>{fmt_ty(r['dn1'])}</td>"
            f"<td style='padding:7px 10px;text-align:right;{bold}'>{fmt_ty(r['dn2'])}</td>"
            f"<td style='padding:7px 10px;text-align:right' {cl_dn}><strong>{delta_str(r['delta_dn'],'tien')}</strong></td>"
            f"<td style='padding:7px 10px;text-align:right;{bold}'>{fmt_pct_vn(r['tl_nqh1'])}</td>"
            f"<td style='padding:7px 10px;text-align:right;{bold}'>{fmt_pct_vn(r['tl_nqh2'])}</td>"
            f"<td style='padding:7px 10px;text-align:right' {cl_nqh}><strong>{delta_str(r['tl_nqh2']-r['tl_nqh1'],'pct')}</strong></td>"
            f"<td style='padding:7px 10px;text-align:right'>{fmt_so(int(r['ho2']))}</td>"
            f"<td style='padding:7px 10px;text-align:right' {cl_dn}>{delta_str(r['delta_ho'],'so')}</td>"
            f"</tr>"
        )

    rows_html = "".join(jn.apply(_row_html, axis=1))
    st.markdown(
        f"""<div style="overflow-x:auto;border-radius:8px;border:1px solid var(--border,#e5e7eb)">
        <table style="width:100%;border-collapse:collapse;font-size:0.85rem">
          <thead>
            <tr style="background:var(--surface-hi,#1e3a5f);color:var(--text-head,white)">
              <th style="padding:9px 10px;text-align:left">Đơn vị</th>
              <th style="padding:9px 10px;text-align:right">DN kỳ {ky1}</th>
              <th style="padding:9px 10px;text-align:right">DN kỳ {ky2}</th>
              <th style="padding:9px 10px;text-align:right">Δ Dư nợ</th>
              <th style="padding:9px 10px;text-align:right">NQH% {ky1}</th>
              <th style="padding:9px 10px;text-align:right">NQH% {ky2}</th>
              <th style="padding:9px 10px;text-align:right">Δ NQH%</th>
              <th style="padding:9px 10px;text-align:right">Số hộ {ky2}</th>
              <th style="padding:9px 10px;text-align:right">Δ Hộ</th>
            </tr>
          </thead>
          <tbody>{rows_html}</tbody>
        </table></div>""",
        unsafe_allow_html=True,
    )


def _render_export_hstd(
    agg_dau: dict, agg_cuoi: dict,
    ky_dau: str, ky_cuoi: str,
    df1: pd.DataFrame, df2: pd.DataFrame,
    username: str, pgd_mode: bool,
) -> None:
    tl1 = tl_nqh(agg_dau["du_no_qh"], agg_dau["tong_du_no"])
    tl2 = tl_nqh(agg_cuoi["du_no_qh"], agg_cuoi["tong_du_no"])
    rows_data = [
        ("Tổng dư nợ (triệu đồng)",
         fmt_ty(agg_dau["tong_du_no"]), fmt_ty(agg_cuoi["tong_du_no"]),
         delta_str(agg_cuoi["tong_du_no"] - agg_dau["tong_du_no"], "tien"),
         pct_change_str(agg_dau["tong_du_no"], agg_cuoi["tong_du_no"])),
        ("Dư nợ trong hạn (triệu đồng)",
         fmt_ty(agg_dau["du_no_th"]), fmt_ty(agg_cuoi["du_no_th"]),
         delta_str(agg_cuoi["du_no_th"] - agg_dau["du_no_th"], "tien"),
         pct_change_str(agg_dau["du_no_th"], agg_cuoi["du_no_th"])),
        ("Dư nợ quá hạn (triệu đồng)",
         fmt_ty(agg_dau["du_no_qh"]), fmt_ty(agg_cuoi["du_no_qh"]),
         delta_str(agg_cuoi["du_no_qh"] - agg_dau["du_no_qh"], "tien"),
         pct_change_str(agg_dau["du_no_qh"], agg_cuoi["du_no_qh"])),
        ("Dư nợ khoanh (triệu đồng)",
         fmt_ty(agg_dau["du_no_khoanh"]), fmt_ty(agg_cuoi["du_no_khoanh"]),
         delta_str(agg_cuoi["du_no_khoanh"] - agg_dau["du_no_khoanh"], "tien"),
         pct_change_str(agg_dau["du_no_khoanh"], agg_cuoi["du_no_khoanh"])),
        ("Tỷ lệ NQH (%)", fmt_pct_vn(tl1), fmt_pct_vn(tl2),
         delta_str(tl2 - tl1, "pct"), "—"),
        ("Số hộ vay",
         fmt_so(int(agg_dau["so_ho"])), fmt_so(int(agg_cuoi["so_ho"])),
         delta_str(agg_cuoi["so_ho"] - agg_dau["so_ho"], "so"),
         pct_change_str(agg_dau["so_ho"], agg_cuoi["so_ho"])),
        ("Giải ngân trong năm (triệu đồng)",
         fmt_ty(agg_dau["gn_nam"]), fmt_ty(agg_cuoi["gn_nam"]),
         delta_str(agg_cuoi["gn_nam"] - agg_dau["gn_nam"], "tien"),
         pct_change_str(agg_dau["gn_nam"], agg_cuoi["gn_nam"])),
    ]
    sheets_extra = None
    if not pgd_mode and not df1.empty and not df2.empty:
        sheets_extra = build_excel_sheets_pgd(df1, df2, ky_dau, ky_cuoi)
    render_export_ui(rows_data, ky_dau, ky_cuoi, username, sheets_extra,
                     action="xuat_bieu_cn", key_prefix="mnk_hstd")


# ─── TAB NQ11 ────────────────────────────────────────────────────────────────

def _render_nq11_tab(
    ky_list_hstd: list[str],
    pgd_mode: bool,
    pgd_user: str | None,
) -> None:
    ds = danh_sach_ky_nq11()
    if len(ds) < 2:
        st.info("ℹ️ Chưa có đủ 2 kỳ NQ11 snapshot.")
        return

    # Mặc định dùng ky_list_hstd nếu có trong ds
    valid_default = [k for k in ky_list_hstd if k in ds]
    default_ky = valid_default[:3] if valid_default else ds[:3]

    ky_chon = st.multiselect(
        "📅 Kỳ NQ11",
        options=ds,
        default=default_ky,
        max_selections=6,
        key="mnk_nq11_ky",
        label_visibility="collapsed",
    )
    if len(ky_chon) < 2:
        st.warning("⚠️ Chọn ít nhất 2 kỳ.")
        return

    ky_sorted = sorted(ky_chon)
    ky_dau, ky_cuoi = ky_sorted[0], ky_sorted[-1]

    def _get_nq11(ky: str) -> dict:
        df = doc_nq11_snapshot(ky)
        if df.empty:
            return {}
        if pgd_mode and pgd_user:
            row = df[df["ten_pgd"] == pgd_user]
        else:
            row = df[df["ten_pgd"] == "__CN__"]
        if row.empty:
            return {}
        return row.iloc[0].to_dict()

    agg_list = [_get_nq11(k) for k in ky_sorted]
    a_dau = agg_list[0]
    a_cuoi = agg_list[-1]

    if not a_dau or not a_cuoi:
        st.warning("⚠️ Không có dữ liệu NQ11 cho các kỳ đã chọn.")
        return

    st.caption(f"NQ11: {ky_dau} → {ky_cuoi} · {len(ky_sorted)} kỳ")

    render_kpi_row([
        {"label": "Tổng dư nợ NQ11 (triệu)", "value": fmt_ty(float(a_cuoi.get("tong_du_no", 0))),
         "delta": float(a_cuoi.get("tong_du_no", 0)) - float(a_dau.get("tong_du_no", 0)), "unit": "tien",
         "help": f"Kỳ {ky_dau}: {fmt_ty(float(a_dau.get('tong_du_no', 0)))}"},
        {"label": "Nợ quá hạn NQ11 (triệu)", "value": fmt_ty(float(a_cuoi.get("no_qh", 0))),
         "delta": float(a_cuoi.get("no_qh", 0)) - float(a_dau.get("no_qh", 0)), "unit": "tien", "inverse": True,
         "help": f"Kỳ {ky_dau}: {fmt_ty(float(a_dau.get('no_qh', 0)))}"},
        {"label": "Số khách hàng NQ11", "value": fmt_so(int(a_cuoi.get("so_kh", 0))),
         "delta": float(a_cuoi.get("so_kh", 0)) - float(a_dau.get("so_kh", 0)), "unit": "so",
         "help": f"Kỳ {ky_dau}: {fmt_so(int(a_dau.get('so_kh', 0)))}"},
        {"label": "Giải ngân NQ11 (triệu)", "value": fmt_ty(float(a_cuoi.get("gn_nam", 0))),
         "delta": float(a_cuoi.get("gn_nam", 0)) - float(a_dau.get("gn_nam", 0)), "unit": "tien",
         "help": f"Kỳ {ky_dau}: {fmt_ty(float(a_dau.get('gn_nam', 0)))}"},
    ])

    st.divider()

    # Xu hướng NQ11
    rows_trend = []
    for ky, a in zip(ky_sorted, agg_list):
        if a:
            rows_trend.append({"ky": ky, "tong_du_no": float(a.get("tong_du_no", 0)),
                                "no_qh": float(a.get("no_qh", 0))})
    df_trend_nq11 = pd.DataFrame(rows_trend) if rows_trend else pd.DataFrame()
    render_trend_chart(df_trend_nq11, ["tong_du_no", "no_qh"],
                       title="Xu hướng dư nợ NQ11 (triệu đồng)", key="mnk_trend_nq11")

    st.divider()

    # Bảng nhiều kỳ
    rows_table = [
        ("Tổng dư nợ NQ11 (triệu đồng)",
         [float(a.get("tong_du_no", 0)) if a else 0.0 for a in agg_list], False, "tien"),
        ("Nợ trong hạn NQ11 (triệu đồng)",
         [float(a.get("no_th", 0)) if a else 0.0 for a in agg_list], False, "tien"),
        ("Nợ quá hạn NQ11 (triệu đồng)",
         [float(a.get("no_qh", 0)) if a else 0.0 for a in agg_list], True, "tien"),
        ("Giải ngân NQ11 (triệu đồng)",
         [float(a.get("gn_nam", 0)) if a else 0.0 for a in agg_list], False, "tien"),
        ("Số khách hàng NQ11",
         [float(a.get("so_kh", 0)) if a else 0.0 for a in agg_list], False, "so"),
    ]
    render_multi_period_table(rows_table, ky_sorted, title="Chỉ tiêu NQ11")


# ─── TAB GQVL ────────────────────────────────────────────────────────────────

def _render_gqvl_tab(
    ky_list_hstd: list[str],
    pgd_mode: bool,
    pgd_user: str | None,
) -> None:
    ds = danh_sach_ky_gqvl()
    if len(ds) < 2:
        st.info("ℹ️ Chưa có đủ 2 kỳ GQVL snapshot.")
        return

    valid_default = [k for k in ky_list_hstd if k in ds]
    default_ky = valid_default[:3] if valid_default else ds[:3]

    ky_chon = st.multiselect(
        "📅 Kỳ GQVL",
        options=ds,
        default=default_ky,
        max_selections=6,
        key="mnk_gqvl_ky",
        label_visibility="collapsed",
    )
    if len(ky_chon) < 2:
        st.warning("⚠️ Chọn ít nhất 2 kỳ.")
        return

    ky_sorted = sorted(ky_chon)
    ky_dau, ky_cuoi = ky_sorted[0], ky_sorted[-1]

    def _get_gqvl(ky: str) -> dict:
        df = doc_gqvl_snapshot(ky)
        if df.empty:
            return {}
        if pgd_mode and pgd_user:
            row = df[df["ten_pgd"] == pgd_user]
        else:
            row = df[df["ten_pgd"] == "__CN__"]
        if row.empty:
            return {}
        return row.iloc[0].to_dict()

    agg_list = [_get_gqvl(k) for k in ky_sorted]
    a_dau = agg_list[0]
    a_cuoi = agg_list[-1]

    if not a_dau or not a_cuoi:
        st.warning("⚠️ Không có dữ liệu GQVL cho các kỳ đã chọn.")
        return

    st.caption(f"GQVL: {ky_dau} → {ky_cuoi} · {len(ky_sorted)} kỳ")

    render_kpi_row([
        {"label": "DN trong hạn GQVL (triệu)", "value": fmt_ty(float(a_cuoi.get("dn_th", 0))),
         "delta": float(a_cuoi.get("dn_th", 0)) - float(a_dau.get("dn_th", 0)), "unit": "tien",
         "help": f"Kỳ {ky_dau}: {fmt_ty(float(a_dau.get('dn_th', 0)))}"},
        {"label": "DN quá hạn GQVL (triệu)", "value": fmt_ty(float(a_cuoi.get("dn_qh", 0))),
         "delta": float(a_cuoi.get("dn_qh", 0)) - float(a_dau.get("dn_qh", 0)), "unit": "tien", "inverse": True,
         "help": f"Kỳ {ky_dau}: {fmt_ty(float(a_dau.get('dn_qh', 0)))}"},
        {"label": "DN khoanh GQVL (triệu)", "value": fmt_ty(float(a_cuoi.get("dn_khoanh", 0))),
         "delta": float(a_cuoi.get("dn_khoanh", 0)) - float(a_dau.get("dn_khoanh", 0)), "unit": "tien", "inverse": True,
         "help": f"Kỳ {ky_dau}: {fmt_ty(float(a_dau.get('dn_khoanh', 0)))}"},
        {"label": "Giải ngân GQVL (triệu)", "value": fmt_ty(float(a_cuoi.get("gn_nam", 0))),
         "delta": float(a_cuoi.get("gn_nam", 0)) - float(a_dau.get("gn_nam", 0)), "unit": "tien",
         "help": f"Kỳ {ky_dau}: {fmt_ty(float(a_dau.get('gn_nam', 0)))}"},
    ])

    st.divider()

    # Xu hướng GQVL
    rows_trend = []
    for ky, a in zip(ky_sorted, agg_list):
        if a:
            rows_trend.append({"ky": ky, "dn_th": float(a.get("dn_th", 0)),
                                "dn_qh": float(a.get("dn_qh", 0))})
    df_trend_gqvl = pd.DataFrame(rows_trend) if rows_trend else pd.DataFrame()
    render_trend_chart(df_trend_gqvl, ["dn_th", "dn_qh"],
                       title="Xu hướng dư nợ GQVL (triệu đồng)", key="mnk_trend_gqvl")

    st.divider()

    rows_table = [
        ("Dư nợ trong hạn (triệu đồng)",
         [float(a.get("dn_th", 0)) if a else 0.0 for a in agg_list], False, "tien"),
        ("Dư nợ quá hạn (triệu đồng)",
         [float(a.get("dn_qh", 0)) if a else 0.0 for a in agg_list], True, "tien"),
        ("Dư nợ khoanh (triệu đồng)",
         [float(a.get("dn_khoanh", 0)) if a else 0.0 for a in agg_list], True, "tien"),
        ("Giải ngân trong năm (triệu đồng)",
         [float(a.get("gn_nam", 0)) if a else 0.0 for a in agg_list], False, "tien"),
        ("Số khách hàng GQVL",
         [float(a.get("so_kh", 0)) if a else 0.0 for a in agg_list], False, "so"),
    ]
    render_multi_period_table(rows_table, ky_sorted, title="Chỉ tiêu GQVL")


# ─── TAB CDTOTKVV ────────────────────────────────────────────────────────────

def _render_cdtotkvv_tab(
    ky_list_hstd: list[str],
    pgd_mode: bool,
    pgd_user: str | None,
) -> None:
    ds = danh_sach_ky_cdtotkvv()
    if len(ds) < 2:
        st.info("ℹ️ Chưa có đủ 2 kỳ Chấm điểm tổ snapshot.")
        return

    valid_default = [k for k in ky_list_hstd if k in ds]
    default_ky = valid_default[:3] if valid_default else ds[:3]

    ky_chon = st.multiselect(
        "📅 Kỳ Chấm điểm tổ",
        options=ds,
        default=default_ky,
        max_selections=6,
        key="mnk_cdt_ky",
        label_visibility="collapsed",
    )
    if len(ky_chon) < 2:
        st.warning("⚠️ Chọn ít nhất 2 kỳ.")
        return

    ky_sorted = sorted(ky_chon)
    ky_dau, ky_cuoi = ky_sorted[0], ky_sorted[-1]

    def _get_cdt(ky: str) -> dict:
        df = doc_cdtotkvv_snapshot(ky)
        if df.empty:
            return {}
        if pgd_mode and pgd_user:
            row = df[df["ten_pgd"] == pgd_user]
            if row.empty:
                row = df[df["ten_pgd"] == "__CN__"]
        else:
            row = df[df["ten_pgd"] == "__CN__"]
        if row.empty:
            return {}
        return row.iloc[0].to_dict()

    agg_list = [_get_cdt(k) for k in ky_sorted]
    a_dau = agg_list[0]
    a_cuoi = agg_list[-1]

    if not a_dau or not a_cuoi:
        st.warning("⚠️ Không có dữ liệu CDTOTKVV cho các kỳ đã chọn.")
        return

    st.caption(f"Chất lượng Tổ TK&VV: {ky_dau} → {ky_cuoi} · {len(ky_sorted)} kỳ")

    render_kpi_row([
        {"label": "Tổng số tổ", "value": fmt_so(int(a_cuoi.get("so_to", 0))),
         "delta": float(a_cuoi.get("so_to", 0)) - float(a_dau.get("so_to", 0)), "unit": "so"},
        {"label": "🟢 Tổ Tốt", "value": fmt_so(int(a_cuoi.get("so_tot", 0))),
         "delta": float(a_cuoi.get("so_tot", 0)) - float(a_dau.get("so_tot", 0)), "unit": "so",
         "help": f"Kỳ {ky_dau}: {fmt_so(int(a_dau.get('so_tot', 0)))}"},
        {"label": "🔵 Tổ Khá", "value": fmt_so(int(a_cuoi.get("so_kha", 0))),
         "delta": float(a_cuoi.get("so_kha", 0)) - float(a_dau.get("so_kha", 0)), "unit": "so",
         "help": f"Kỳ {ky_dau}: {fmt_so(int(a_dau.get('so_kha', 0)))}"},
        {"label": "🟡 Tổ Trung bình", "value": fmt_so(int(a_cuoi.get("so_tb", 0))),
         "delta": float(a_cuoi.get("so_tb", 0)) - float(a_dau.get("so_tb", 0)), "unit": "so", "inverse": True,
         "help": f"Kỳ {ky_dau}: {fmt_so(int(a_dau.get('so_tb', 0)))}"},
    ])
    render_kpi_row([
        {"label": "🔴 Tổ Yếu", "value": fmt_so(int(a_cuoi.get("so_yeu", 0))),
         "delta": float(a_cuoi.get("so_yeu", 0)) - float(a_dau.get("so_yeu", 0)), "unit": "so", "inverse": True,
         "help": f"Kỳ {ky_dau}: {fmt_so(int(a_dau.get('so_yeu', 0)))}"},
        {"label": "📊 Điểm TB", "value": f"{float(a_cuoi.get('diem_tb', 0)):.2f}",
         "delta": float(a_cuoi.get("diem_tb", 0)) - float(a_dau.get("diem_tb", 0)), "unit": "pct",
         "help": f"Kỳ {ky_dau}: {float(a_dau.get('diem_tb', 0)):.2f}"},
        {"label": "", "value": "", "delta": None},
        {"label": "", "value": "", "delta": None},
    ])

    st.divider()

    # Xu hướng điểm TB
    rows_trend = []
    for ky, a in zip(ky_sorted, agg_list):
        if a:
            rows_trend.append({"ky": ky, "diem_tb": float(a.get("diem_tb", 0)),
                                "so_tot": float(a.get("so_tot", 0)),
                                "so_yeu": float(a.get("so_yeu", 0))})
    df_trend_cdt = pd.DataFrame(rows_trend) if rows_trend else pd.DataFrame()
    render_trend_chart(df_trend_cdt, "diem_tb",
                       title="Xu hướng Điểm trung bình", y_label="Điểm", key="mnk_trend_diem_tb")

    st.divider()

    # Bảng nhiều kỳ
    rows_table = [
        ("Tổng số tổ",
         [float(a.get("so_to", 0)) if a else 0.0 for a in agg_list], False, "so"),
        ("Tổ xếp loại Tốt",
         [float(a.get("so_tot", 0)) if a else 0.0 for a in agg_list], False, "so"),
        ("Tổ xếp loại Khá",
         [float(a.get("so_kha", 0)) if a else 0.0 for a in agg_list], False, "so"),
        ("Tổ Trung bình",
         [float(a.get("so_tb", 0)) if a else 0.0 for a in agg_list], True, "so"),
        ("Tổ xếp loại Yếu",
         [float(a.get("so_yeu", 0)) if a else 0.0 for a in agg_list], True, "so"),
        ("Điểm TB",
         [float(a.get("diem_tb", 0)) if a else 0.0 for a in agg_list], False, "pct"),
    ]
    render_multi_period_table(rows_table, ky_sorted, title="Chỉ tiêu chất lượng tổ")

    # Pie charts kỳ đầu vs kỳ cuối
    if not pgd_mode:
        st.divider()
        st.markdown("**📊 Cơ cấu xếp loại tổ** *(kỳ đầu vs kỳ cuối)*")
        try:
            col1, col2 = st.columns(2)
            labels_pie = ["Tốt", "Khá", "Trung bình", "Yếu"]
            colors_pie = ["#16a34a", "#2563eb", "#f59e0b", "#dc2626"]
            for col, a, lbl in [(col1, a_dau, ky_dau), (col2, a_cuoi, ky_cuoi)]:
                vals = [float(a.get("so_tot", 0)), float(a.get("so_kha", 0)),
                        float(a.get("so_tb", 0)), float(a.get("so_yeu", 0))]
                fig_pie = go.Figure(go.Pie(
                    labels=labels_pie, values=vals,
                    marker_colors=colors_pie,
                    hole=0.35,
                    textinfo="label+percent",
                ))
                fig_pie.update_layout(
                    title=dict(text=f"Kỳ {lbl}", font_size=13),
                    height=300,
                    margin=dict(t=40, b=10, l=10, r=10),
                    showlegend=False,
                )
                col.plotly_chart(fig_pie, use_container_width=True,
                                 key=f"mnk_pie_cdt_{lbl.replace('-', '_')}")
        except Exception:
            pass


# ─── RENDER CHÍNH ────────────────────────────────────────────────────────────

def render_nhieu_ky(tab: DeltaGenerator = None, **kwargs) -> None:
    """Entry point: so sánh nhiều kỳ với 4 tabs ngang."""
    ctx = TabContext(tab, **kwargs)
    role = normalize_role(str(kwargs.get("role", "user")))
    username = kwargs.get("username", "unknown")
    pgd_user = kwargs.get("pgd_user")
    pgd_mode = bool(kwargs.get("pgd_mode", False)) or (
        pgd_user is not None and la_phan_he_pgd(role)
    )

    with ctx:
        st.subheader("📊 So sánh nhiều kỳ")

        ds_ky = danh_sach_ky()
        if len(ds_ky) < 2:
            st.warning("⚠️ Cần ít nhất **2 kỳ snapshot** để so sánh.")
            return

        # Thu thập danh sách PGD từ kỳ gần nhất
        pgd_data_list: list[str] = []
        if not pgd_mode:
            df_latest = doc_snapshot(ds_ky[0])
            pgd_data_list = sorted(
                p for p in df_latest["ten_pgd"].unique()
                if not str(p).startswith("__")
            ) if not df_latest.empty else []

        ky_list, pgd_filter = _render_bo_loc(ds_ky, pgd_mode, pgd_user, pgd_data_list)
        if not ky_list:
            return

        st.divider()

        lazy_tabs(
            ["📊 HSTD", "📋 NQ11", "💼 GQVL", "🏆 CDTOTKVV"],
            [
                lambda c: _render_hstd_tab(ky_list, pgd_mode, pgd_user, pgd_filter, username),
                lambda c: _render_nq11_tab(ky_list, pgd_mode, pgd_user),
                lambda c: _render_gqvl_tab(ky_list, pgd_mode, pgd_user),
                lambda c: _render_cdtotkvv_tab(ky_list, pgd_mode, pgd_user),
            ],
            key="so_sanh_nhieu_ky_dataset",
        )
